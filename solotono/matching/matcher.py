"""Product Matching Engine for SoloTono, implementing SoloTodo's 3-stage entity association."""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple
from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from solotono.config import MATCH_FUZZY_THRESHOLD, MATCH_PENDING_THRESHOLD
from solotono.db.models import Entity, Product
from solotono.matching.normalizer import analyze_product_string, strip_accents
from solotono.matching.taxonomy import classify_product


@dataclass
class MatchResult:
    entity_id: int
    matched_product_id: Optional[int]
    confidence: float
    match_strategy: str  # "exact_mpn", "exact_ean", "fuzzy_token", "pending_review", "created_new"
    candidate_products: List[Tuple[int, str, float]]  # [(product_id, name, score)]


class ProductMatcher:
    """Orchestrates 3-stage matching: Deterministic (MPN/EAN) -> Semantic Fuzzy -> Pending Queue."""

    def __init__(self, session: Session, fuzzy_threshold: float = MATCH_FUZZY_THRESHOLD, pending_threshold: float = MATCH_PENDING_THRESHOLD):
        self.session = session
        self.fuzzy_threshold = fuzzy_threshold
        self.pending_threshold = pending_threshold

    def _propagate_image(self, product: Optional[Product], entity: Entity):
        """If the canonical product lacks an image, update it with the entity's primary image."""
        if product and (not product.picture_url or product.picture_url.strip() == ""):
            if entity.picture_urls:
                first_img = entity.picture_urls.split(",")[0].strip()
                if first_img:
                    product.picture_url = first_img

    def match_entity(self, entity: Entity, auto_create_canonical: bool = False) -> MatchResult:
        """Evaluate an Entity against existing Products and associate if confidence is high."""
        # If entity is already associated, preserve association (SoloTodo rule) and ensure picture is synced
        if entity.is_associated and entity.product_id:
            existing_prod = self.session.query(Product).filter(Product.id == entity.product_id).first()
            self._propagate_image(existing_prod, entity)
            return MatchResult(
                entity_id=entity.id,
                matched_product_id=entity.product_id,
                confidence=1.0,
                match_strategy="already_associated",
                candidate_products=[],
            )

        analysis = analyze_product_string(entity.name, raw_brand=entity.brand, sku=entity.sku)
        brand = analysis["brand"]
        mpn = entity.part_number or analysis["part_number"]
        ean = entity.ean
        norm_model = analysis["normalized_model"]

        # =========================================================================
        # Stage 1: Exact Match (MPN or EAN) - Only across DIFFERENT stores
        # =========================================================================
        if mpn and len(mpn) >= 4:
            exact_by_mpn = self.session.query(Product).filter(Product.part_number == mpn).first()
            # Store Exclusivity: Candidate cannot already contain an entity from the same store!
            if exact_by_mpn and not any(e.store_id == entity.store_id for e in exact_by_mpn.entities):
                entity.product_id = exact_by_mpn.id
                entity.is_associated = True
                self._propagate_image(exact_by_mpn, entity)
                return MatchResult(
                    entity_id=entity.id,
                    matched_product_id=exact_by_mpn.id,
                    confidence=1.0,
                    match_strategy="exact_mpn",
                    candidate_products=[(exact_by_mpn.id, exact_by_mpn.name, 1.0)],
                )

        if ean and len(ean) >= 8:
            exact_by_ean = self.session.query(Product).filter(Product.ean == ean).first()
            # Store Exclusivity: Candidate cannot already contain an entity from the same store!
            if exact_by_ean and not any(e.store_id == entity.store_id for e in exact_by_ean.entities):
                entity.product_id = exact_by_ean.id
                entity.is_associated = True
                self._propagate_image(exact_by_ean, entity)
                return MatchResult(
                    entity_id=entity.id,
                    matched_product_id=exact_by_ean.id,
                    confidence=1.0,
                    match_strategy="exact_ean",
                    candidate_products=[(exact_by_ean.id, exact_by_ean.name, 1.0)],
                )

        # =========================================================================
        # Stage 2: Semantic Fuzzy Token Matching (CROSS-STORE ONLY)
        # =========================================================================
        query = self.session.query(Product)
        if brand:
            # Filter candidates by matching brand (flexible punctuation to bridge e.g. Electro-Voice vs Electrovoice)
            clean_b = re.sub(r"[^a-zA-Z0-9]+", "%", brand).strip("%")
            query = query.filter(Product.brand.ilike(f"%{clean_b}%"))
        candidates = query.all()

        # STORE EXCLUSIVITY: A store does not match against its own products.
        # Exclude any canonical product that already has an offer from entity.store_id!
        candidates = [
            c for c in candidates
            if not any(e.store_id == entity.store_id for e in c.entities)
        ]

        scored_candidates: List[Tuple[Product, float]] = []
        for cand in candidates:
            cand_analysis = analyze_product_string(cand.name, raw_brand=cand.brand, sku=cand.part_number)
            cand_norm = cand_analysis["normalized_model"]
            if not norm_model or not cand_norm:
                continue

            # 1. Hard Disjunction: Series conflict (e.g. Ultra vs Vintage vs Professional vs Player)
            cand_series = cand_analysis["series_tokens"]
            ent_series = analysis["series_tokens"]
            if cand_series and ent_series and not cand_series.intersection(ent_series):
                continue

            # 2. Hard Disjunction: Year conflict (e.g. 1957 vs 1960 or vintage year in one but absent in other)
            cand_years = cand_analysis["year_tokens"]
            ent_years = analysis["year_tokens"]
            if (cand_years or ent_years) and cand_years != ent_years:
                continue

            # 3. Hard Disjunction: Finish / Color conflict (e.g. Sinister Red vs Solar Flare)
            cand_f = cand_analysis["finish"].lower() if cand_analysis["finish"] else None
            ent_f = analysis["finish"].lower() if analysis["finish"] else None
            if (cand_f is not None or ent_f is not None) and (cand_f != ent_f):
                continue

            # 4. Hard Disjunction: Alphanumeric Model Code conflict (e.g. M50X vs M20X, UM2 vs UMC22, CT-S400 vs CT-S100, 114CE vs 24CE)
            cand_codes = cand_analysis["model_codes"]
            ent_codes = analysis["model_codes"]
            if cand_codes and ent_codes and not cand_codes.intersection(ent_codes):
                continue

            # 5. Hard Disjunction: Fretboard Wood conflict (e.g. Maple vs Rosewood)
            cand_wood = cand_analysis.get("fretboard")
            ent_wood = analysis.get("fretboard")
            if cand_wood and ent_wood and cand_wood != ent_wood:
                continue

            # 6. Hard Disjunction: Pickup Configuration conflict (e.g. HSS vs SSS)
            cand_pu = cand_analysis.get("pickup_config")
            ent_pu = analysis.get("pickup_config")
            if cand_pu and ent_pu and cand_pu != ent_pu:
                continue

            # 7. Hard Disjunction: Size / Fractional / Inch dimension conflict (e.g. 3/4 vs 4/4, 15" vs 12")
            cand_size = cand_analysis.get("size_spec")
            ent_size = analysis.get("size_spec")
            if cand_size and ent_size and cand_size != ent_size:
                continue

            # 8. Hard Disjunction: Multi-pack quantity conflict (e.g. Pack of 5 vs Single item)
            cand_pack = cand_analysis.get("pack_qty")
            ent_pack = analysis.get("pack_qty")
            if (cand_pack or ent_pack) and cand_pack != ent_pack:
                continue

            # Token sort ratio strictly penalizes extraneous and missing tokens
            score_sort = fuzz.token_sort_ratio(norm_model, cand_norm)
            base_score = score_sort / 100.0

            # If alphanumeric model codes match explicitly (e.g. both '1204usb' or both 'xs1') and zero conflicts,
            # require baseline token similarity >= 0.70 to avoid accidental short-code collisions:
            if cand_codes and ent_codes and cand_codes.intersection(ent_codes) and base_score >= 0.70:
                score = max(base_score, 0.95)
            else:
                score = base_score

            if score >= self.pending_threshold:
                scored_candidates.append((cand, score))

        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        if scored_candidates:
            best_cand, best_score = scored_candidates[0]
            candidate_list = [(c.id, c.name, s) for c, s in scored_candidates[:5]]

            if best_score >= self.fuzzy_threshold:
                # High confidence match!
                entity.product_id = best_cand.id
                entity.is_associated = True
                self._propagate_image(best_cand, entity)
                return MatchResult(
                    entity_id=entity.id,
                    matched_product_id=best_cand.id,
                    confidence=best_score,
                    match_strategy="fuzzy_token",
                    candidate_products=candidate_list,
                )
            else:
                # Stage 3: Ambiguous match -> Pending Queue
                entity.is_associated = False
                return MatchResult(
                    entity_id=entity.id,
                    matched_product_id=None,
                    confidence=best_score,
                    match_strategy="pending_review",
                    candidate_products=candidate_list,
                )

        # =========================================================================
        # Auto-create Canonical Product (if requested and brand is known)
        # =========================================================================
        if auto_create_canonical and brand:
            canonical_name = analysis.get("clean_title") or entity.name.replace("®", "").replace("™", "").strip()
            tax_res = classify_product(canonical_name, raw_category=entity.category, brand=brand, session=self.session)

            new_prod = Product(
                name=canonical_name,
                brand=brand,
                category_id=tax_res.category_id,
                category=tax_res.category_name or entity.category or "Guitarras Eléctricas",
                part_number=mpn,
                ean=ean,
                picture_url=entity.picture_urls.split(",")[0] if entity.picture_urls else None,
            )
            self.session.add(new_prod)
            self.session.flush()  # Generate new_prod.id

            entity.product_id = new_prod.id
            if tax_res.category_id:
                entity.category_id = tax_res.category_id
            entity.is_associated = True
            return MatchResult(
                entity_id=entity.id,
                matched_product_id=new_prod.id,
                confidence=1.0,
                match_strategy="created_new",
                candidate_products=[(new_prod.id, new_prod.name, 1.0)],
            )

        # No match found -> remains unassociated in pending queue
        entity.is_associated = False
        return MatchResult(
            entity_id=entity.id,
            matched_product_id=None,
            confidence=0.0,
            match_strategy="pending_review",
            candidate_products=[],
        )

    def match_all_unassociated(self, auto_create_canonical: bool = False) -> List[MatchResult]:
        """Process all unassociated entities currently in the database."""
        unassociated = self.session.query(Entity).filter(Entity.is_associated == False).all()
        results: List[MatchResult] = []
        for ent in unassociated:
            res = self.match_entity(ent, auto_create_canonical=auto_create_canonical)
            results.append(res)
        self.session.commit()
        return results
