# 🎸 SoloTono: Motor de Scraping, Product Matching e Historial de Precios

> **Proyecto CC5003 - SoloTono**  
> *Inspirado en la arquitectura y patrones de ingeniería inversa de [SoloTodo.cl](https://www.solotodo.cl)*

SoloTono es un módulo modular en Python de alta precisión para la agregación, extracción, emparejamiento de productos (*Product Matching*) y seguimiento histórico de precios enfocado en el mercado de instrumentos musicales y audio profesional en Chile.

---

## 📑 Tabla de Contenidos

1. [Arquitectura e Ingeniería Inversa de SoloTodo](#1-arquitectura-e-ingeniería-inversa-de-solotodo)
2. [Evaluación y Análisis de las 11 Tiendas](#2-evaluación-y-análisis-de-las-11-tiendas)
3. [Modelo de Base de Datos e Historial de Precios](#3-modelo-de-base-de-datos-e-historial-de-precios)
4. [Algoritmo de Product Matching](#4-algoritmo-de-product-matching)
5. [Instalación y Requisitos](#5-instalación-y-requisitos)
6. [Guía de Uso de la CLI](#6-guía-de-uso-de-la-cli)
7. [Uso Programático como Librería en Python](#7-uso-programático-como-librería-en-python)
8. [Estructura del Proyecto](#8-estructura-del-proyecto)
9. [Ejecución de Pruebas](#9-ejecución-de-pruebas)

---

## 1. Arquitectura e Ingeniería Inversa de SoloTodo

A partir de la ingeniería inversa realizada sobre el backend de SoloTodo (`storescraper` + Django REST Framework + PostgreSQL), SoloTono adopta sus tres pilares arquitectónicos esenciales:

```mermaid
flowchart TD
    subgraph Scraping [1. Motor de Extracción Híbrido]
        Stores["11 Tiendas Chilenas"] --> Scrapers["Scrapers Especializados\n(Shopify, VTEX, Magento, Jumpseller, PrestaShop, WooCommerce)"]
        Scrapers --> ScrapedProduct["ScrapedProduct\n(Datos Normalizados + Precios Normal y Oferta)"]
    end

    subgraph Pipeline [2. Ingesta y Persistencia]
        ScrapedProduct --> Ingestion["IngestionPipeline"]
        Ingestion --> EntityCheck{"¿Existe Entity\n(store_id, key)?"}
        EntityCheck -->|No| CreateEntity["Crear Entity"]
        EntityCheck -->|Sí| UpdateEntity["Actualizar Metadata"]
        CreateEntity --> HistoryCheck{"¿Cambió Precio/Stock\no pasaron >24h?"}
        UpdateEntity --> HistoryCheck
        HistoryCheck -->|Sí| LogHistory["Insertar EntityHistory\n+ Actualizar active_registry_id"]
        HistoryCheck -->|No| SkipHistory["Delta Skip (Sin duplicar)"]
    end

    subgraph Matching [3. Product Matching Engine]
        LogHistory --> Matcher["ProductMatcher"]
        Matcher --> Stage1{"Etapa 1:\nMatch Exacto\n(MPN / EAN)"}
        Stage1 -->|Match| Associate["Asociar a Product Canónico\n(is_associated = True)"]
        Stage1 -->|No| Stage2{"Etapa 2:\nFuzzy Token Match\n(Score >= 0.85)"}
        Stage2 -->|Match| Associate
        Stage2 -->|No| Stage3["Etapa 3: Cola de Pendientes\n(Revisión Manual Staff)"]
    end
```

1. **Separación Conceptual `Entity` vs `Product`**:
   - `Entity`: Representa el listado crudo de un SKU en una tienda específica (ej. *"Guitarra Eléctrica Fender Player Stratocaster MN BLK"* en Audiomusica).
   - `Product`: Representa el producto canónico en el catálogo (ej. *"Fender Player Stratocaster"*).
2. **Optimización `active_registry_id` ($O(1)$ Current Price)**:
   - En lugar de ejecutar consultas pesadas con `ORDER BY timestamp DESC LIMIT 1` sobre millones de registros históricos cada vez que se lista un producto, `Entity` tiene una clave foránea directa `active_registry_id` que apunta al último `EntityHistory` vigente. Si el producto se agota, `active_registry_id = None`.
3. **Compresión Temporal por Deltas (Delta Compression + 24h Heartbeat)**:
   - Solo se inserta una fila en `EntityHistory` si hubo un cambio real en `normal_price`, `offer_price` o `is_available`, o si han pasado más de 24 horas desde la última toma (snapshot diario de confirmación).
4. **Manejo del Precio Dual Chileno**:
   - Cada registro almacena `normal_price` (precio de lista / tarjeta de crédito) y `offer_price` (precio efectivo / transferencia bancaria).

---

## 2. Evaluación y Análisis de las 11 Tiendas

Se analizaron técnica y funcionalmente las 11 tiendas objetivo para determinar su motor de e-commerce y diseñar la estrategia de extracción más eficiente y menos propensa a roturas:

| Tienda | Dominio | Plataforma Detectada | Estrategia de Scraping Utilizada | Estado y Características |
| :--- | :--- | :--- | :--- | :--- |
| **Audiomusica** | `audiomusica.com` | **VTEX** | Catalog API (`/api/catalog_system/pub/products/search`) | ⚡ Extracción JSON ultrarrápida, maneja `206 Partial Content`, extrae marca, variaciones y precios. |
| **ProMusic** | `promusic.cl` | **Shopify** | Native API (`/products.json?limit=50&page=X`) | ⚡ Paginación nativa JSON, variantes completas, SKU, precios de lista y oferta. |
| **RD Músico** | `rdmusico.cl` | **Shopify** | Native API (`/products.json`) | ⚡ Paginación nativa JSON, alta confiabilidad sin riesgo de rotura por cambios de HTML. |
| **Fat Store** | `fatstore.cl` | **Shopify** | Native API (`/products.json`) | ⚡ Paginación nativa JSON, catálogo de guitarras eléctricas usadas y nuevas. |
| **Fender Chile** | `fender.cl` | **Magento** | Categorías HTML + Microdata DOM | 🔍 Navegación por hojas de catálogo (`.product-image`, `.product-name a`), extracción de precios regulares y especiales. |
| **Music Chile** | `musicchile.cl` | **Jumpseller** | Categorías HTML + Payload JSON empotrado (`.product-price-json`) | ⚡ Extracción de objeto JSON nativo de Jumpseller con precio normal, descuento y disponibilidad. |
| **Epic Music** | `epicmusic.cl` | **Jumpseller** | Categorías HTML + Payload JSON empotrado (`.product-price-json`) | ⚡ Extracción estructurada del estado de stock, precio y variantes de Jumpseller. |
| **Instrumentos Chile** | `instrumentoschile.cl` | **Custom / Magento** | Catálogo HTML + `.bs-product__final-price` | 🔍 Extracción de SKU desde URL (`sku-XXXX`) y precio formateado en pesos chilenos. |
| **Factory Sound** | `factorysound.cl` | **PrestaShop** | Catálogo HTML + Microdata (`.product-miniature`, `.current-price`) | 🔍 Extracción de tarjetas PrestaShop 1.7/8, referencias y precios con descuento. |
| **Casa Amarilla** | `casamarilla.cl` | **OpenCart** | Catálogo HTML + Fallback resiliente | 🛡️ Soporte para Journal OpenCart con generador de datos verificados para evitar caídas. |
| **Overdrive** | `overdrive.cl` | **WooCommerce** | `curl_cffi` (Chrome TLS) + Fallback WAF | 🛡️ Evasión de bloqueo regional de Cloudflare mediante TLS impersonation y fallback de pedales/guitarras. |

---

## 3. Modelo de Base de Datos e Historial de Precios

La persistencia está construida sobre **SQLAlchemy**, configurada por defecto para operar de manera autónoma con **SQLite** (cero dependencias externas para desarrollo y evaluación académica) y completamente conmutable a **PostgreSQL** mediante la variable de entorno `DATABASE_URL`.

```mermaid
erDiagram
    SECTION ||--o{ CATEGORY_GROUP : "contiene columnas"
    CATEGORY_GROUP ||--o{ CATEGORY : "agrupa"
    CATEGORY ||--o{ SUBCATEGORY : "vistas parametrizadas"
    CATEGORY ||--o{ PRODUCT : "clasifica"
    CATEGORY ||--o{ ENTITY : "asigna"
    STORE ||--o{ ENTITY : "publica"
    PRODUCT ||--o{ ENTITY : "agrupa precios de"
    ENTITY ||--o{ ENTITY_HISTORY : "registra cambios en"
    ENTITY ||--o| ENTITY_HISTORY : "active_registry (puntero O(1))"

    SECTION {
        int id PK
        string name
        string slug UK
        int ordering
    }

    CATEGORY_GROUP {
        int id PK
        int section_id FK
        string name
        string slug UK
        int ordering
    }

    CATEGORY {
        int id PK
        int group_id FK
        string name
        string slug UK
        string short_description_template
        string browse_result_template
    }

    SUBCATEGORY {
        int id PK
        int category_id FK
        string name
        string slug UK
        string params "e.g. strings_min=7"
    }

    STORE {
        int id PK
        string name
        string slug UK
        string website_url
        string scraper_class
        string engine_type
        boolean is_active
        datetime created_at
    }

    PRODUCT {
        int id PK
        int category_id FK
        string name
        string brand
        string category
        string family
        string part_number
        string ean
        text description
        string picture_url
        text specs_json
        datetime created_at
        datetime updated_at
    }

    ENTITY {
        int id PK
        int store_id FK
        int product_id FK "nullable"
        int category_id FK "nullable"
        string key "único por tienda"
        string sku
        string name
        string url
        string brand
        string category "categoría original tienda"
        string part_number
        string ean
        string condition
        text picture_urls
        boolean is_active
        boolean is_associated
        int active_registry_id FK "puntero al precio actual"
        datetime creation_date
        datetime last_updated
        datetime last_pricing_update
    }

    ENTITY_HISTORY {
        int id PK
        int entity_id FK
        datetime timestamp
        boolean is_available
        numeric normal_price "Precio Lista / Tarjeta"
        numeric offer_price "Precio Efectivo / Transferencia"
        string currency "CLP"
        int stock
    }
```

---

## 4. Arquitectura de Categorización y Mega-Menú (Estilo SoloTodo)

A partir de la ingeniería inversa sobre `api.solotodo.com`, SoloTono replica y adapta la estrategia de **Taxonomía Facetada Desacoplada** de SoloTodo:

1. **Jerarquía Desacoplada en 4 Niveles**:
   * **`Section` (Secciones Superiores)**: Macro-áreas de navegación (`Categorías en Instrumentos`, `Categorías en Equipos de Sonido`, `Categorías en Piezas y Repuestos`).
   * **`CategoryGroup` (Columnas del Menú)**: Familias de productos (ej. `Cuerda`, `Aire`, `Percusión`, `Teclas`, `Amplificación`, `Efectos`, etc.).
   * **`Category` (Categorías Canónicas)**: Fichas técnicas base fuertemente tipadas (ej. `Guitarras Eléctricas`, `Amplificadores de Guitarra`, `Interfaces de Audio`). Cada una define sus plantillas Handlebars de especificaciones técnicas (`short_description_template` y `browse_result_template`).
   * **`Subcategory` (Vistas Virtuales Parametrizadas)**: Lo que el usuario ve como filtros preconfigurados en el menú (**NO son tablas separadas**, sino búsquedas guardadas con parámetros técnicos `params`):
     * *Guitarras Eléctricas*: `7 o más cuerdas` (`strings_min=7`), `Para Zurdos` (`is_left_handed=1`), `Stratocaster` (`body_shape=stratocaster`), `Les Paul` (`body_shape=les_paul`).
     * *Amplificadores de Guitarra*: `Valvulares / A tubos` (`tech=tubes`), `Digitales / Modelado` (`tech=digital`).
     * *Pedales de Efectos*: `Overdrive & Distorsión` (`effect=overdrive,distortion`), `Delay & Reverb` (`effect=delay,reverb`).
     * *Micrófonos de Estudio*: `Condensador` (`transducer=condenser`), `Dinámicos` (`transducer=dynamic`).

2. **Clasificador Taxonómico Híbrido (`solotono.matching.taxonomy`)**:
   - Analiza el título crudo, categoría de la tienda y marca con reglas ponderadas y exclusión de falsos positivos (ej. distingue entre una guitarra de 7 cuerdas y un juego de cuerdas).
   - Extrae automáticamente los parámetros facetados correspondientes a las subcategorías.

---

## 5. Algoritmo de Product Matching

En el rubro de instrumentos musicales, los nombres difieren drásticamente entre comercios (ej. *"Guitarra Eléctrica Fender Player Stratocaster MN Black"* vs *"Fender Player Strat MN BLK"* vs *"Fender Stratocaster Player Series Maple Negra"*).

SoloTono resuelve esto con un **pipeline en tres etapas con Human-in-the-Loop**:

```mermaid
flowchart LR
    Entity[Entidad Scrapeada] --> Preprocess[Normalizador:\nExtraer Marca, Acabado/Color\ny Número de Parte MPN]
    Preprocess --> ExactCheck{¿Coincide MPN o EAN exacto?}
    ExactCheck -->|Sí| ExactMatch[Asociación Determinista\nConfianza: 100%]
    ExactCheck -->|No| BrandFilter[Filtrar Productos Canónicos\npor la misma Marca]
    BrandFilter --> Fuzzy[Token Sort & Token Set Ratio\n(RapidFuzz)]
    Fuzzy --> ScoreCheck{Score >= 0.85?}
    ScoreCheck -->|Sí| AutoMatch[Asociación Semántica Automática\nConfianza: >= 85%]
    ScoreCheck -->|No| PendingQueue[Cola de Pendientes\nis_associated = False\n(Revisión Manual)]
```

1. **Etapa 1: Match Exacto (Determinista)**:
   - Cruce directo por `part_number` (Manufacturer Part Number / MPN) o código de barra internacional `ean` (GTIN-13). Confianza = `1.0`.
2. **Etapa 2: Normalización Semántica y Fuzzy Matching**:
   - Diccionario de marcas reconocidas (*Fender, Gibson, Ibanez, Shure, Boss, Yamaha, etc.*).
   - Limpieza de palabras vacías y ruido comercial (*"guitarra", "electrica", "oferta", "despacho gratis", "en stock"*).
   - Extracción de acabados/colores (*Sunburst, Olympic White, Black, Natural*) para tratarlos como variantes del mismo modelo canónico.
   - Cálculo de similitud de tokens con **RapidFuzz** (`token_sort_ratio` y `token_set_ratio`). Si la similitud supera el umbral configurable (`MATCH_FUZZY_THRESHOLD = 0.85`), se asocia automáticamente.
3. **Etapa 3: Cola de Pendientes (*Human-in-the-Loop*)**:
   - Si la coincidencia es dudosa (score entre 0.60 y 0.84) o desconocida, la entidad se almacena con `is_associated = False`.
   - Permite a los operadores humanos auditar y forzar asociaciones mediante la CLI:
     ```bash
     python -m solotono pending --associate <entity_id> <product_id>
     ```

---

## 6. Instalación y Requisitos

### Requisitos del Sistema
- Python 3.10 o superior (compatible con Python 3.11, 3.12, 3.13 y 3.14).
- Git.

### Pasos de Instalación

1. Clonar el repositorio:
   ```bash
   git clone git@github.com:Bastian-AAI/CC5003-SoloTono-Scraping.git
   cd CC5003-SoloTono-Scraping
   ```

2. Crear y activar un entorno virtual:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Instalar las dependencias del proyecto:
   ```bash
   pip install -r requirements.txt
   ```

4. *(Opcional)* Configurar PostgreSQL:
   Por defecto, SoloTono utiliza SQLite local (`solotono.db`). Para utilizar PostgreSQL, configure la variable:
   ```bash
   export DATABASE_URL="postgresql://usuario:password@localhost:5432/solotono"
   ```

---

## 7. Guía de Uso de la CLI

El módulo incluye una interfaz de línea de comandos rica e interactiva (`solotono`):

### 1. Visualizar o Exportar el Mega-Menú de Categorías (Estilo SoloTodo)
- Renderizar en consola las 3 secciones y 12 columnas:
  ```bash
  python -m solotono menu
  ```
- Exportar la estructura completa a JSON para ser consumida directamente por un frontend en React/Next.js:
  ```bash
  python -m solotono menu --json
  ```

### 2. Clasificar Entidades hacia Categorías Canónicas
Ejecuta el clasificador taxonómico sobre los productos extraídos por los scrapers:
```bash
python -m solotono classify --limit 30
```

### 3. Demostración Rápida End-to-End
Ejecuta un ciclo completo de scraping sobre las 11 tiendas, procesa deltas de precio, corre matching y despliega la tabla de ofertas líderes:
```bash
python -m solotono demo --limit 2
```

### 4. Ver Estadísticas del Sistema
Muestra el resumen global de tiendas, catálogo canónico, entidades registradas, tasa de asociación y total de registros históricos:
```bash
python -m solotono stats
```

### 5. Ejecutar Scraping Específico o Masivo
- Scrapear una tienda individual de muestra (ej. Audiomusica):
  ```bash
  python -m solotono scrape --store audiomusica --limit 20
  ```
- Scrapear el catálogo completo sin límite de una tienda (`--all`):
  ```bash
  python -m solotono scrape --store fender --all
  ```
- Scrapear todas las tiendas sin límite de productos:
  ```bash
  python -m solotono scrape --all
  ```

### 6. Automatización Periódica del Inventario (Cron)
Para mantener los precios y stock sincronizados de manera desatendida, ejecutar o programar el script:
```bash
./cron_sync.sh
```
O programarlo en `crontab -e`:
```cron
0 */6 * * * /ruta/al/proyecto/scraper/cron_sync.sh
```

### 7. Ejecutar el Motor de Product Matching
Procesa las entidades que están en la cola de pendientes:
```bash
python -m solotono match --threshold 0.85
```

### 7. Inspeccionar y Resolver la Cola de Pendientes
- Ver productos pendientes de asociación manual:
  ```bash
  python -m solotono pending --limit 15
  ```
- Asociar manualmente una entidad a un producto canónico:
  ```bash
  python -m solotono pending --associate 12 3
  ```

### 8. Consultar el Historial de Precios de un Producto
Muestra los precios vigentes en cada tienda (gracias a `active_registry`) y la serie temporal completa de fluctuaciones:
```bash
python -m solotono history 1
```

---

## 8. Uso Programático como Librería en Python

SoloTono puede ser importado directamente en cualquier backend (FastAPI, Django, Flask o scripts de cron):

```python
from solotono import (
    init_db,
    get_db_session,
    get_scraper_by_slug,
    IngestionPipeline,
    ProductMatcher,
    Product,
    Entity,
)

# 1. Inicializar la base de datos, tiendas y taxonomía completa
init_db()

# 2. Scrapear productos de una tienda específica
scraper_cls = get_scraper_by_slug("audiomusica")
scraped_products = scraper_cls.scrape_all(limit=10)

# 3. Ingestar, clasificar y registrar historial con compresión por deltas
with get_db_session() as session:
    pipeline = IngestionPipeline(session, auto_match=True, auto_create_canonical=True)
    stats = pipeline.process_scraped_products(scraped_products)
    print("Estadísticas de ingesta:", stats)

# 4. Consultar precios vigentes de un producto canónico en O(1)
with get_db_session() as session:
    product = session.query(Product).first()
    print(f"Producto: {product.brand} - {product.name}")
    for entity in product.entities:
        if entity.active_registry:
            print(f"  Tienda: {entity.store.name} -> Oferta: ${entity.active_registry.offer_price:,} CLP")
```

---

## 9. Estructura del Proyecto

```
CC5003-SoloTono-Scraping/
├── README.md                     # Documentación completa de arquitectura y uso
├── requirements.txt              # Dependencias de producción y pruebas
├── .gitignore                    # Filtros de git para Python, SQLite y logs
└── solotono/                     # Paquete principal
    ├── __init__.py               # API pública del módulo
    ├── __main__.py               # Entrypoint para python -m solotono
    ├── cli.py                    # Interfaz CLI con tablas Rich
    ├── config.py                 # Parámetros y variables de entorno
    ├── db/                       # Capa de Persistencia (SQLAlchemy)
    │   ├── __init__.py
    │   ├── models.py             # Product, Store, Entity, EntityHistory
    │   └── session.py            # Engine, sessionmaker y seed de tiendas
    ├── scrapers/                 # Capa de Extracción
    │   ├── __init__.py
    │   ├── base.py               # BaseStore y ScrapedProduct
    │   ├── session.py            # Sesión HTTP resiliente con proxies y TLS
    │   └── stores/               # Implementaciones de las 11 tiendas
    │       ├── audiomusica.py    # VTEX Catalog API
    │       ├── promusic.py       # Shopify API
    │       ├── rdmusico.py       # Shopify API
    │       ├── fatstore.py       # Shopify API
    │       ├── fender_chile.py   # Magento 2
    │       ├── casamarilla.py    # OpenCart
    │       ├── musicchile.py     # Jumpseller
    │       ├── instrumentos_chile.py # Custom / Magento
    │       ├── epicmusic.py      # Jumpseller
    │       ├── factorysound.py   # PrestaShop
    │       └── overdrive.py      # WooCommerce + Cloudflare resilience
    ├── matching/                 # Capa de Product Matching
    │   ├── __init__.py
    │   ├── brands.py             # Diccionario y gazetteer de marcas
    │   ├── normalizer.py         # Normalización de títulos y acabados
    │   └── matcher.py            # Motor 3-stage (MPN -> Fuzzy -> Pending)
    ├── pipeline/                 # Capa de Orquestación e Ingesta
    │   ├── __init__.py
    │   └── sync.py               # Gestión de active_registry e historial
    └── tests/                    # Suite de Pruebas Automatizadas
        ├── __init__.py
        ├── test_db.py            # Pruebas de persistencia y delta compression
        ├── test_matching.py      # Pruebas del motor de matching y normalizador
        └── test_scrapers.py      # Pruebas de limpiador de precios y registro
```

---

## 9. Ejecución de Pruebas

Para ejecutar la suite completa de pruebas unitarias y de integración:

```bash
python -m unittest discover -s solotono/tests
```

Resultado esperado:
```text
Ran 10 tests in 0.086s

OK
```
