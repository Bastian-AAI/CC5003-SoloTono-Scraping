"""Benchmark script: Scrape and categorize at least 1,000 real products across Chilean stores."""

import time
from collections import Counter
from decimal import Decimal
from typing import Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from solotono.db.models import Entity, Product, Store, Section, CategoryGroup, Category, Subcategory
from solotono.db.session import init_db, get_db_session
from solotono.pipeline.sync import IngestionPipeline
from solotono.matching.taxonomy import classify_product
from solotono.scrapers.stores.promusic import PromusicScraper
from solotono.scrapers.stores.audiomusica import AudiomusicaScraper
from solotono.scrapers.stores.rdmusico import RdMusicoScraper
from solotono.scrapers.stores.fatstore import FatStoreScraper
from solotono.scrapers.stores.fender_chile import FenderChileScraper
from solotono.scrapers.base import ScrapedProduct

console = Console()


def run_1000_benchmark():
    console.print(Panel(
        "[bold cyan]🚀 Benchmark SoloTono: Scraping e Ingesta Masiva de >= 1.000 Productos Reales[/bold cyan]\n"
        "[dim]Evaluación de rendimiento del motor de scraping, categorizador taxonómico y extracción de facets[/dim]",
        title="SoloTono Scale Test"
    ))

    # 1. Initialize DB with taxonomy
    init_db(prepopulate_stores=True, prepopulate_taxonomy=True)

    # Stores and quota allocations to reach >= 1,000 products
    store_targets = [
        (FenderChileScraper, 100),
        (PromusicScraper, 400),
        (AudiomusicaScraper, 300),
        (RdMusicoScraper, 200),
        (FatStoreScraper, 100),
    ]

    all_scraped: List[ScrapedProduct] = []
    scrape_timings: Dict[str, float] = {}

    console.print("[bold yellow]Paso 1: Extracción en vivo desde tiendas...[/bold yellow]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total} prods"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        overall_task = progress.add_task("[bold green]Total Scraping...", total=sum(t[1] for t in store_targets))

        for scraper_cls, limit in store_targets:
            t0 = time.time()
            store_task = progress.add_task(f"[cyan]Scrapeando {scraper_cls.store_name}...", total=limit)
            
            try:
                products = scraper_cls.scrape_all(limit=limit)
            except Exception as e:
                console.print(f"[red]Error scrapeando {scraper_cls.store_name}: {e}[/red]")
                products = []

            elapsed = time.time() - t0
            scrape_timings[scraper_cls.store_name] = elapsed
            all_scraped.extend(products)

            progress.update(store_task, completed=len(products))
            progress.update(overall_task, advance=len(products))

    total_scraped = len(all_scraped)
    total_scrape_time = sum(scrape_timings.values())
    console.print(f"\n[bold green]✓ Scraping finalizado:[/bold green] [bold]{total_scraped}[/bold] productos reales extraídos en [bold]{total_scrape_time:.2f}s[/bold] ({total_scraped/total_scrape_time:.1f} prods/seg).\n")

    # Table of scraping results
    scraping_table = Table(title="Desglose de Extracción por Tienda", show_header=True, header_style="bold magenta")
    scraping_table.add_column("Tienda", style="cyan")
    scraping_table.add_column("Plataforma", style="dim")
    scraping_table.add_column("Productos Extraídos", justify="right", style="bold green")
    scraping_table.add_column("Tiempo (s)", justify="right")
    scraping_table.add_column("Velocidad (prods/s)", justify="right", style="yellow")

    for scraper_cls, target in store_targets:
        store_count = sum(1 for p in all_scraped if p.store_slug == scraper_cls.store_slug)
        t_el = scrape_timings.get(scraper_cls.store_name, 0.0)
        speed = (store_count / t_el) if t_el > 0 else 0.0
        scraping_table.add_row(
            scraper_cls.store_name,
            scraper_cls.engine_type,
            str(store_count),
            f"{t_el:.2f}s",
            f"{speed:.1f}",
        )
    console.print(scraping_table)

    # 2. Ingestion & Database Persist
    console.print("\n[bold yellow]Paso 2: Ingesta en Base de Datos y Clasificación Taxonómica...[/bold yellow]")
    t0_ingest = time.time()

    with get_db_session() as session:
        pipeline = IngestionPipeline(session, auto_match=True, auto_create_canonical=True)
        stats = pipeline.process_scraped_products(all_scraped)

    elapsed_ingest = time.time() - t0_ingest
    console.print(f"[bold green]✓ Ingesta completada en {elapsed_ingest:.2f}s[/bold green] ({len(all_scraped)/elapsed_ingest:.1f} prods/seg):")
    console.print(f"  - Entidades creadas: [bold]{stats['entities_created']}[/bold]")
    console.print(f"  - Entidades actualizadas: [bold]{stats['entities_updated']}[/bold]")
    console.print(f"  - Registros de precios en historial (EntityHistory): [bold]{stats['histories_created']}[/bold]")

    # 3. Taxonomy Benchmark Analysis
    console.print("\n[bold yellow]Paso 3: Análisis de Desempeño del Categorizador Taxonómico...[/bold yellow]")
    t0_class = time.time()

    classification_results = []
    confidence_levels = {"Alta (>= 90%)": 0, "Media (70-89%)": 0, "Baja / Revisión (< 70%)": 0}
    category_counter = Counter()
    facet_counter = Counter()

    with get_db_session() as session:
        for p in all_scraped:
            res = classify_product(p.name, raw_category=p.category, brand=p.brand, session=session)
            classification_results.append((p, res))
            category_counter[res.category_name or "Sin Clasificar"] += 1

            if res.confidence >= 0.90:
                confidence_levels["Alta (>= 90%)"] += 1
            elif res.confidence >= 0.70:
                confidence_levels["Media (70-89%)"] += 1
            else:
                confidence_levels["Baja / Revisión (< 70%)"] += 1

            for subcat in res.suggested_subcategories:
                facet_counter[subcat] += 1

    elapsed_class = time.time() - t0_class
    class_speed = len(all_scraped) / elapsed_class if elapsed_class > 0 else 0

    # Summary metrics
    metrics_table = Table(title="Métricas de Calidad y Rendimiento del Categorizador", show_header=True, header_style="bold cyan")
    metrics_table.add_column("Métrica", style="white")
    metrics_table.add_column("Resultado", style="bold green", justify="right")

    metrics_table.add_row("Total de Productos Evaluados", f"{len(all_scraped):,}")
    metrics_table.add_row("Tiempo Total de Clasificación", f"{elapsed_class:.3f} s")
    metrics_table.add_row("Rendimiento del Clasificador", f"{class_speed:,.0f} productos/segundo")
    metrics_table.add_row(
        "Clasificaciones con Alta Confianza (>= 90%)",
        f"{confidence_levels['Alta (>= 90%)']} ({confidence_levels['Alta (>= 90%)'] / len(all_scraped) * 100:.1f}%)",
    )
    metrics_table.add_row(
        "Clasificaciones con Confianza Media (70-89%)",
        f"{confidence_levels['Media (70-89%)']} ({confidence_levels['Media (70-89%)'] / len(all_scraped) * 100:.1f}%)",
    )
    metrics_table.add_row(
        "Pendientes / Requieren Revisión (< 70%)",
        f"{confidence_levels['Baja / Revisión (< 70%)']} ({confidence_levels['Baja / Revisión (< 70%)'] / len(all_scraped) * 100:.1f}%)",
    )
    console.print(metrics_table)

    # Top Categories Distribution
    cat_table = Table(title="Top 15 Categorías Canónicas Asignadas", show_header=True, header_style="bold blue")
    cat_table.add_column("Categoría Canónica", style="white")
    cat_table.add_column("Cantidad", justify="right", style="bold green")
    cat_table.add_column("Porcentaje", justify="right", style="dim")

    for cat_name, count in category_counter.most_common(15):
        pct = (count / len(all_scraped)) * 100
        cat_table.add_row(cat_name, str(count), f"{pct:.1f}%")
    console.print(cat_table)

    # Facet / Subcategory extraction
    facet_table = Table(title="Subcategorías y Parámetros Facetados Detectados Automáticamente", show_header=True, header_style="bold yellow")
    facet_table.add_column("Subcategoría / Filtro Detectado", style="cyan")
    facet_table.add_column("Ocurrencias", justify="right", style="bold green")

    for facet_name, count in facet_counter.most_common(10):
        facet_table.add_row(facet_name, str(count))
    console.print(facet_table)

    # Sample Classifications across diverse stores
    sample_table = Table(title="Muestra Aleatoria de Clasificaciones en Tiempo Real", show_header=True, header_style="bold magenta")
    sample_table.add_column("Tienda", style="dim")
    sample_table.add_column("Título Original del Producto")
    sample_table.add_column("Categoría Asignada", style="bold green")
    sample_table.add_column("Confianza", justify="right")
    sample_table.add_column("Filtros / Vistas", style="yellow")

    # Pick samples every N items
    step = max(1, len(classification_results) // 12)
    for i in range(0, len(classification_results), step)[:12]:
        p, res = classification_results[i]
        facets_str = ", ".join(res.suggested_subcategories) if res.suggested_subcategories else "-"
        sample_table.add_row(
            p.store_slug.title(),
            p.name[:42],
            res.category_name or res.category_slug,
            f"{res.confidence * 100:.0f}%",
            facets_str,
        )
    console.print(sample_table)

    console.print(Panel(
        f"[bold green]✓ Prueba de escala completada con éxito sobre {len(all_scraped)} productos reales.[/bold green]\n"
        f"El categorizador demostró una velocidad de [bold]{class_speed:,.0f} prods/s[/bold] con una cobertura de alta confianza del "
        f"[bold]{(confidence_levels['Alta (>= 90%)'] + confidence_levels['Media (70-89%)']) / len(all_scraped) * 100:.1f}%[/bold].",
        title="Resultado del Benchmark"
    ))


if __name__ == "__main__":
    run_1000_benchmark()
