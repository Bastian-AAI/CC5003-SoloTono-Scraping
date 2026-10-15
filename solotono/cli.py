"""Rich interactive Command Line Interface for SoloTono."""

import argparse
import sys
from decimal import Decimal
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

import json
from solotono.db.models import Entity, EntityHistory, Product, Store, Section, CategoryGroup, Category, Subcategory
from solotono.db.session import get_db_session, init_db
from solotono.matching.matcher import ProductMatcher
from solotono.matching.taxonomy import classify_product
from solotono.pipeline.sync import IngestionPipeline
from solotono.scrapers.stores import SCRAPER_REGISTRY, get_scraper_by_slug

console = Console()


def format_clp(amount: Optional[Decimal]) -> str:
    """Format Decimal amount as CLP currency string."""
    if amount is None:
        return "$0"
    return f"${int(amount):,}".replace(",", ".")


def cmd_stats(args):
    """Display system and database statistics."""
    with get_db_session() as session:
        total_stores = session.query(Store).count()
        total_products = session.query(Product).count()
        total_entities = session.query(Entity).count()
        associated_entities = session.query(Entity).filter(Entity.is_associated == True).count()
        pending_entities = session.query(Entity).filter(Entity.is_associated == False).count()
        active_in_stock = session.query(Entity).filter(Entity.active_registry_id != None).count()
        total_histories = session.query(EntityHistory).count()

        pct_associated = (associated_entities / total_entities * 100) if total_entities > 0 else 0

        table = Table(title="🎸 SoloTono Database & Scraping Stats", show_header=True, header_style="bold magenta")
        table.add_column("Métrica", style="cyan")
        table.add_column("Valor", style="green", justify="right")

        table.add_row("Tiendas Registradas", str(total_stores))
        table.add_row("Productos Canónicos (Catálogo)", str(total_products))
        table.add_row("Entidades de Tiendas (SKUs)", str(total_entities))
        table.add_row("Entidades Asociadas", f"{associated_entities} ({pct_associated:.1f}%)")
        table.add_row("Entidades en Cola Pendiente", str(pending_entities))
        table.add_row("Entidades Activas con Stock (active_registry)", str(active_in_stock))
        table.add_row("Registros en Historial de Precios", f"{total_histories:,}")

        console.print(table)


def cmd_init_db(args):
    """Initialize database tables and seed taxonomy and store definitions."""
    console.print("[bold blue]Inicializando esquema de base de datos y fixtures...[/bold blue]")
    init_db(prepopulate_stores=True, prepopulate_taxonomy=True, drop_first=getattr(args, "drop", False))
    console.print("[bold green]✓ Base de datos inicializada exitosamente con tiendas y taxonomía.[/bold green]")


def cmd_scrape(args):
    """Run scraping for a specific store or all stores."""
    init_db(prepopulate_stores=True)

    slugs = [args.store] if args.store else list(SCRAPER_REGISTRY.keys())
    console.print(f"[bold cyan]Iniciando scraping para {len(slugs)} tienda(s)...[/bold cyan]")

    with get_db_session() as session:
        pipeline = IngestionPipeline(
            session,
            auto_match=args.auto_match,
            auto_create_canonical=args.auto_create,
        )

        table = Table(title="Resultados del Scraping", show_header=True, header_style="bold green")
        table.add_column("Tienda", style="cyan")
        table.add_column("Plataforma", style="dim")
        table.add_column("Scrapeados", justify="right")
        table.add_column("Nuevos", justify="right")
        table.add_column("Actualizados", justify="right")
        table.add_column("Historiales", justify="right")
        table.add_column("Asociados", justify="right")

        effective_limit = None if (getattr(args, "all", False) or (args.limit is not None and args.limit <= 0)) else args.limit

        for slug in slugs:
            scraper_cls = get_scraper_by_slug(slug)
            with Progress(SpinnerColumn(), TextColumn(f"[bold blue]Scrapeando {scraper_cls.store_name}..."), transient=True) as progress:
                progress.add_task("scrape", total=None)
                try:
                    products = scraper_cls.scrape_all(limit=effective_limit)
                    stats = pipeline.process_scraped_products(products)
                    table.add_row(
                        scraper_cls.store_name,
                        scraper_cls.engine_type,
                        str(stats["total_processed"]),
                        str(stats["entities_created"]),
                        str(stats["entities_updated"]),
                        str(stats["histories_created"]),
                        str(stats["matched_entities"]),
                    )
                except Exception as e:
                    table.add_row(scraper_cls.store_name, scraper_cls.engine_type, "ERROR", "-", "-", "-", str(e))

        console.print(table)


def cmd_match(args):
    """Run product matching on unassociated entities."""
    with get_db_session() as session:
        matcher = ProductMatcher(session, fuzzy_threshold=args.threshold)
        unassociated = session.query(Entity).filter(Entity.is_associated == False).all()

        console.print(f"[bold yellow]Ejecutando Product Matching en {len(unassociated)} entidades pendientes...[/bold yellow]")

        matched_count = 0
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("ID Entidad", style="dim", justify="right")
        table.add_column("Nombre Tienda (Entidad)")
        table.add_column("Producto Canónico Asignado", style="green")
        table.add_column("Estrategia", style="blue")
        table.add_column("Confianza", justify="right")

        for ent in unassociated:
            res = matcher.match_entity(ent, auto_create_canonical=args.auto_create)
            if res.matched_product_id:
                matched_count += 1
                prod = session.query(Product).get(res.matched_product_id)
                table.add_row(
                    str(ent.id),
                    ent.name[:40],
                    prod.name[:40] if prod else "Nuevo Creado",
                    res.match_strategy,
                    f"{res.confidence * 100:.0f}%",
                )

        session.commit()
        console.print(table)
        console.print(f"[bold green]✓ Matching completado: {matched_count}/{len(unassociated)} entidades asociadas.[/bold green]")


def cmd_pending(args):
    """Manage the human-in-the-loop pending queue."""
    with get_db_session() as session:
        if args.associate:
            # Format: solotono pending --associate <entity_id> <product_id>
            entity_id, product_id = args.associate
            ent = session.query(Entity).get(entity_id)
            prod = session.query(Product).get(product_id)
            if not ent:
                console.print(f"[bold red]Error: No existe la entidad con ID {entity_id}[/bold red]")
                return
            if not prod:
                console.print(f"[bold red]Error: No existe el producto con ID {product_id}[/bold red]")
                return
            ent.product_id = prod.id
            ent.is_associated = True
            session.commit()
            console.print(f"[bold green]✓ Entidad #{ent.id} ('{ent.name}') asociada exitosamente al Producto #{prod.id} ('{prod.name}')[/bold green]")
            return

        # List pending
        pending = session.query(Entity).filter(Entity.is_associated == False).limit(args.limit or 20).all()
        table = Table(title=f"Cola de Pendientes (Revisión Manual SoloTodo Staff)", show_header=True, header_style="bold yellow")
        table.add_column("ID", style="dim", justify="right")
        table.add_column("Tienda", style="cyan")
        table.add_column("Nombre Producto")
        table.add_column("Precio Actual", justify="right", style="green")
        table.add_column("Marca", style="blue")
        table.add_column("MPN / SKU", style="dim")

        for p in pending:
            price = p.active_registry.offer_price if p.active_registry else None
            table.add_row(
                str(p.id),
                p.store.name if p.store else str(p.store_id),
                p.name[:45],
                format_clp(price),
                p.brand or "-",
                p.part_number or p.sku or "-",
            )

        console.print(table)
        console.print("[dim]Para asociar manualmente: [bold]solotono pending --associate <entity_id> <product_id>[/bold][/dim]")


def cmd_history(args):
    """Show price history for a canonical product across all stores."""
    with get_db_session() as session:
        prod = session.query(Product).get(args.product_id)
        if not prod:
            console.print(f"[bold red]Producto #{args.product_id} no encontrado.[/bold red]")
            return

        console.print(Panel(f"[bold cyan]{prod.brand}[/bold cyan] - [bold white]{prod.name}[/bold white]\nCategoría: {prod.category} | MPN: {prod.part_number or 'N/A'}", title="Ficha de Producto"))

        # Current offers
        entities = session.query(Entity).filter(Entity.product_id == prod.id).all()
        curr_table = Table(title="Precios Actuales por Tienda (O(1) active_registry)", show_header=True, header_style="bold green")
        curr_table.add_column("Tienda", style="cyan")
        curr_table.add_column("Estado", justify="center")
        curr_table.add_column("Precio Normal", justify="right")
        curr_table.add_column("Precio Oferta", justify="right", style="bold green")
        curr_table.add_column("URL Tienda", style="dim")

        for e in entities:
            if e.active_registry:
                curr_table.add_row(
                    e.store.name,
                    "[green]En Stock[/green]",
                    format_clp(e.active_registry.normal_price),
                    format_clp(e.active_registry.offer_price),
                    e.url[:50] + "...",
                )
            else:
                curr_table.add_row(e.store.name, "[red]Agotado[/red]", "-", "-", e.url[:50] + "...")

        console.print(curr_table)

        # Time series history
        histories = (
            session.query(EntityHistory, Store.name)
            .join(Entity, EntityHistory.entity_id == Entity.id)
            .join(Store, Entity.store_id == Store.id)
            .filter(Entity.product_id == prod.id)
            .order_by(EntityHistory.timestamp.desc())
            .limit(args.limit or 30)
            .all()
        )

        hist_table = Table(title="Historial de Precios Temporal (EntityHistory)", show_header=True, header_style="bold blue")
        hist_table.add_column("Fecha y Hora", style="dim")
        hist_table.add_column("Tienda", style="cyan")
        hist_table.add_column("Precio Normal", justify="right")
        hist_table.add_column("Precio Oferta", justify="right", style="green")
        hist_table.add_column("Disponible", justify="center")

        for h, store_name in histories:
            hist_table.add_row(
                h.timestamp.strftime("%Y-%m-%d %H:%M"),
                store_name,
                format_clp(h.normal_price),
                format_clp(h.offer_price),
                "✓" if h.is_available else "✗",
            )

        console.print(hist_table)


def cmd_demo(args):
    """Run an end-to-end demo: scrape samples from stores, match products, and show comparison."""
    init_db(prepopulate_stores=True)

    console.print(Panel(
        "[bold green]🎸 Bienvenido a SoloTono: Comparador de Precios de Instrumentos Musicales en Chile[/bold green]\n"
        "[dim]Inspirado en la arquitectura de SoloTodo (Scraping modular, Product Matching, active_registry, EntityHistory)[/dim]",
        title="Demo End-to-End SoloTono"
    ))

    limit_per_store = args.limit or 2
    console.print(f"[bold cyan]1. Ejecutando scraping rápido en las tiendas registradas (límite {limit_per_store} productos c/u)...[/bold cyan]")

    with get_db_session() as session:
        pipeline = IngestionPipeline(session, auto_match=True, auto_create_canonical=True)

        for slug in list(SCRAPER_REGISTRY.keys()):
            scraper_cls = get_scraper_by_slug(slug)
            try:
                products = scraper_cls.scrape_all(limit=limit_per_store)
                stats = pipeline.process_scraped_products(products)
                console.print(f"  [green]✓[/green] [bold]{scraper_cls.store_name:<20}[/bold] ({scraper_cls.engine_type:<10}) -> {len(products)} scrapeados, {stats['histories_created']} registros de precio.")
            except Exception as e:
                console.print(f"  [red]✗[/red] [bold]{scraper_cls.store_name}[/bold] -> Error: {e}")

        # Show comparison on products with multiple store prices or best deals
        console.print("\n[bold cyan]2. Comparativa de Precios por Producto Canónico (SoloTodo style):[/bold cyan]")

        products = session.query(Product).all()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID", justify="right", style="dim")
        table.add_column("Marca", style="blue")
        table.add_column("Producto Canónico", style="white")
        table.add_column("Mejor Precio Oferta", justify="right", style="bold green")
        table.add_column("Precio Normal", justify="right", style="dim")
        table.add_column("Tienda Líder", style="cyan")

        for prod in products[:10]:
            # Find entities with active registry
            active_ents = [e for e in prod.entities if e.active_registry_id]
            if not active_ents:
                continue
            # Sort by offer price
            best_ent = min(active_ents, key=lambda e: e.active_registry.offer_price)
            table.add_row(
                str(prod.id),
                prod.brand,
                prod.name[:45],
                format_clp(best_ent.active_registry.offer_price),
                format_clp(best_ent.active_registry.normal_price),
                best_ent.store.name,
            )

        console.print(table)
        console.print("[dim]Usa [bold]python -m solotono history <id>[/bold] para ver el desglose e historial temporal completo de un producto.[/dim]\n")


def cmd_menu(args):
    """Display or export the complete SoloTodo-style Mega-Menu taxonomy."""
    init_db(prepopulate_stores=True, prepopulate_taxonomy=True)

    with get_db_session() as session:
        sections = session.query(Section).order_by(Section.ordering).all()

        if args.json:
            export_data = []
            for sec in sections:
                sec_dict = {
                    "id": sec.id,
                    "name": sec.name,
                    "slug": sec.slug,
                    "groups": []
                }
                for grp in sec.groups:
                    grp_dict = {
                        "id": grp.id,
                        "name": grp.name,
                        "slug": grp.slug,
                        "categories": []
                    }
                    for cat in grp.categories:
                        cat_dict = {
                            "id": cat.id,
                            "name": cat.name,
                            "slug": cat.slug,
                            "subcategories": [
                                {
                                    "id": sub.id,
                                    "name": sub.name,
                                    "slug": sub.slug,
                                    "params": sub.params,
                                }
                                for sub in cat.subcategories
                            ]
                        }
                        grp_dict["categories"].append(cat_dict)
                    sec_dict["groups"].append(grp_dict)
                export_data.append(sec_dict)
            print(json.dumps(export_data, indent=2, ensure_ascii=False))
            return

        console.print(Panel(
            "[bold orange3]🎸 Mega-Menú de Categorización SoloTono (Arquitectura SoloTodo)[/bold orange3]\n"
            "[dim]Organizado en Secciones > Grupos (Columnas) > Categorías Canónicas > Subcategorías (Filtros)[/dim]",
            title="Estructura de Navegación del Catálogo"
        ))

        for sec in sections:
            console.print(f"\n[bold dark_orange]{sec.name.upper()}[/bold dark_orange]")
            table = Table(show_header=True, header_style="bold cyan", border_style="dim")
            
            for grp in sec.groups:
                table.add_column(grp.name, style="white", min_width=25)

            # Max categories in any group of this section
            max_cats = max(len(grp.categories) for grp in sec.groups) if sec.groups else 0

            for i in range(max_cats):
                row = []
                for grp in sec.groups:
                    if i < len(grp.categories):
                        cat = grp.categories[i]
                        sub_count = len(cat.subcategories)
                        badge = f" [dim]({sub_count} vistas)[/dim]" if sub_count > 0 else ""
                        row.append(f"{cat.name}{badge}")
                    else:
                        row.append("")
                table.add_row(*row)

            # Footer "Ver todos" row like SoloTodo screenshots
            table.add_row(*["[bold orange3]Ver todos[/bold orange3]" for _ in sec.groups])
            console.print(table)


def cmd_classify(args):
    """Run taxonomic classification on store entities."""
    init_db(prepopulate_stores=True, prepopulate_taxonomy=True)

    with get_db_session() as session:
        query = session.query(Entity)
        if not args.all:
            query = query.filter(Entity.category_id == None)
        entities = query.limit(args.limit).all()

        console.print(f"[bold cyan]Clasificando {len(entities)} entidades con el clasificador taxonómico...[/bold cyan]")

        table = Table(title="Clasificación Taxonómica de Entidades", show_header=True, header_style="bold green")
        table.add_column("ID", style="dim", justify="right")
        table.add_column("Tienda", style="cyan")
        table.add_column("Título Crudo")
        table.add_column("Categoría Canónica Asignada", style="bold green")
        table.add_column("Confianza", justify="right")
        table.add_column("Facets / Subcats", style="yellow")

        for ent in entities:
            res = classify_product(ent.name, raw_category=ent.category, brand=ent.brand, session=session)
            if res.category_id:
                ent.category_id = res.category_id
            subcat_str = ", ".join(res.suggested_subcategories) if res.suggested_subcategories else "-"
            table.add_row(
                str(ent.id),
                ent.store.name if ent.store else "-",
                ent.name[:38],
                res.category_name or res.category_slug,
                f"{res.confidence * 100:.0f}%",
                subcat_str,
            )

        session.commit()
        console.print(table)
        console.print(f"[bold green]✓ Clasificación completada para {len(entities)} entidades.[/bold green]")


def main():
    parser = argparse.ArgumentParser(
        prog="solotono",
        description="SoloTono: Motor de Scraping, Product Matching e Historial de Precios de Instrumentos Musicales en Chile.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")

    # Command: menu
    p_menu = subparsers.add_parser("menu", help="Visualizar o exportar el mega-menú de categorías estilo SoloTodo")
    p_menu.add_argument("--json", action="store_true", help="Exportar estructura jerárquica en formato JSON")

    # Command: classify
    p_classify = subparsers.add_parser("classify", help="Clasificar entidades hacia categorías canónicas")
    p_classify.add_argument("--limit", type=int, default=50, help="Límite de entidades a clasificar")
    p_classify.add_argument("--all", action="store_true", help="Reclasificar todas las entidades, incluso las ya asignadas")

    # Command: demo
    p_demo = subparsers.add_parser("demo", help="Ejecutar demo end-to-end rápido")
    p_demo.add_argument("--limit", type=int, default=2, help="Límite de productos por tienda")

    # Command: stats
    p_stats = subparsers.add_parser("stats", help="Mostrar estadísticas de la base de datos")

    # Command: scrape
    p_scrape = subparsers.add_parser("scrape", help="Ejecutar scraping de tiendas")
    p_scrape.add_argument("--store", type=str, default=None, help="Slug de tienda específica")
    p_scrape.add_argument("--limit", type=int, default=10, help="Límite de productos a extraer (0 para sin límite)")
    p_scrape.add_argument("--all", action="store_true", help="Extraer el catálogo completo de las tiendas sin límite")
    p_scrape.add_argument("--auto-match", action="store_true", default=True, help="Ejecutar matching automático al guardar")
    p_scrape.add_argument("--auto-create", action="store_true", default=True, help="Crear producto canónico si no existe")

    # Command: match
    p_match = subparsers.add_parser("match", help="Ejecutar Product Matching sobre entidades pendientes")
    p_match.add_argument("--threshold", type=float, default=0.90, help="Umbral de confianza fuzzy (0.0 - 1.0)")
    p_match.add_argument("--auto-create", action="store_true", default=False, help="Crear producto canónico para no coincidentes")

    # Command: pending
    p_pending = subparsers.add_parser("pending", help="Inspeccionar y resolver cola de pendientes (revisión manual)")
    p_pending.add_argument("--limit", type=int, default=20, help="Límite de pendientes a listar")
    p_pending.add_argument("--associate", nargs=2, type=int, metavar=("ENTITY_ID", "PRODUCT_ID"), help="Asociar manualmente una entidad a un producto canónico")

    # Command: init-db
    p_init = subparsers.add_parser("init-db", help="Inicializar esquema de base de datos y fixtures de tiendas/taxonomía")
    p_init.add_argument("--drop", action="store_true", help="Eliminar tablas existentes antes de recrear el esquema")

    # Command: history
    p_hist = subparsers.add_parser("history", help="Ver historial de precios de un producto canónico")
    p_hist.add_argument("product_id", type=int, help="ID del producto canónico")
    p_hist.add_argument("--limit", type=int, default=30, help="Límite de registros temporales")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    commands = {
        "init-db": cmd_init_db,
        "menu": cmd_menu,
        "classify": cmd_classify,
        "demo": cmd_demo,
        "stats": cmd_stats,
        "scrape": cmd_scrape,
        "match": cmd_match,
        "pending": cmd_pending,
        "history": cmd_history,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()

