"""Product Matching Engine for SoloTono, implementing SoloTodo's 3-stage entity association."""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from solotono.config import MATCH_FUZZY_THRESHOLD, MATCH_PENDING_THRESHOLD
from solotono.db.models import Entity, Product
from solotono.matching.normalizer import analyze_product_string, strip_accents


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

    def match_entity(self, entity: Entity, auto_create_canonical: bool = False) -> MatchResult:
        """Evaluate an Entity against existing Products and associate if confidence is high."""
        # If entity is already associated, preserve association (SoloTodo rule)
        if entity.is_associated and entity.product_id:
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
        # Stage 1: Exact Match (MPN or EAN)
        # =========================================================================
        if mpn and len(mpn) >= 4:
            exact_by_mpn = self.session.query(Product).filter(Product.part_number == mpn).first()
            if exact_by_mpn:
                entity.product_id = exact_by_mpn.id
                entity.is_associated = True
                return MatchResult(
                    entity_id=entity.id,
                    matched_product_id=exact_by_mpn.id,
                    confidence=1.0,
                    match_strategy="exact_mpn",
                    candidate_products=[(exact_by_mpn.id, exact_by_mpn.name, 1.0)],
                )

        if ean and len(ean) >= 8:
            exact_by_ean = self.session.query(Product).filter(Product.ean == ean).first()
            if exact_by_ean:
                entity.product_id = exact_by_ean.id
                entity.is_associated = True
                return MatchResult(
                    entity_id=entity.id,
                    matched_product_id=exact_by_ean.id,
                    confidence=1.0,
                    match_strategy="exact_ean",
                    candidate_products=[(exact_by_ean.id, exact_by_ean.name, 1.0)],
                )

        # =========================================================================
        # Stage 2: Semantic Fuzzy Token Matching
        # =========================================================================
        query = self.session.query(Product)
        if brand:
            # Filter candidates by matching brand to prevent cross-brand false positives
            query = query.filter(Product.brand.ilike(f"%{brand}%"))
        candidates = query.all()

        scored_candidates: List[Tuple[Product, float]] = []
        for cand in candidates:
            cand_norm = analyze_product_string(cand.name, raw_brand=cand.brand)["normalized_model"]
            if not norm_model or not cand_norm:
                continue

            # Token sort ratio handles word order variations
            score_sort = fuzz.token_sort_ratio(norm_model, cand_norm)
            score_set = fuzz.token_set_ratio(norm_model, cand_norm)
            score = max(score_sort, score_set) / 100.0

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
            # Clean title for canonical catalog
            canonical_name = entity.name.replace("®", "").replace("™", "").strip()
            new_prod = Product(
                name=canonical_name,
                brand=brand,
                category=entity.category or "Instrumentos",
                part_number=mpn,
                ean=ean,
                picture_url=entity.picture_urls.split(",")[0] if entity.picture_urls else None,
            )
            self.session.add(new_prod)
            self.session.flush()  # Generate new_prod.id

            entity.product_id = new_prod.id
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
