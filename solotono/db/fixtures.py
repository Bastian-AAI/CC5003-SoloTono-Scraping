"""Taxonomy seed data and fixtures for SoloTono, matching SoloTodo's menu structure."""

from typing import Dict, List, Any
from sqlalchemy.orm import Session

from solotono.db.models import Section, CategoryGroup, Category, Subcategory


TAXONOMY_FIXTURES: List[Dict[str, Any]] = [
    {
        "name": "Categorías en Instrumentos",
        "slug": "instrumentos",
        "ordering": 1,
        "groups": [
            {
                "name": "Cuerda",
                "slug": "cuerda",
                "ordering": 1,
                "categories": [
                    {
                        "name": "Guitarras Eléctricas",
                        "slug": "guitarras-electricas",
                        "ordering": 1,
                        "short_description_template": "{{ body_wood }} / {{ fretboard_wood }} / {{ pickups_config }}",
                        "browse_result_template": "<dl><dt>Cápsulas</dt><dd>{{pickups_config}}</dd><dt>Cuerpo</dt><dd>{{body_wood}}</dd><dt>Trastes</dt><dd>{{frets_count}}</dd></dl>",
                        "subcategories": [
                            {"name": "7 o más cuerdas", "slug": "guitarras-electricas-7-cuerdas", "params": "strings_min=7", "ordering": 1},
                            {"name": "Para Zurdos", "slug": "guitarras-electricas-zurdos", "params": "is_left_handed=1", "ordering": 2},
                            {"name": "Stratocaster", "slug": "guitarras-electricas-stratocaster", "params": "body_shape=stratocaster", "ordering": 3},
                            {"name": "Les Paul / Singlecut", "slug": "guitarras-electricas-les-paul", "params": "body_shape=les_paul", "ordering": 4},
                            {"name": "Telecaster", "slug": "guitarras-electricas-telecaster", "params": "body_shape=telecaster", "ordering": 5},
                        ],
                    },
                    {
                        "name": "Guitarras Acústicas",
                        "slug": "guitarras-acusticas",
                        "ordering": 2,
                        "subcategories": [
                            {"name": "Electroacústicas", "slug": "guitarras-electroacusticas", "params": "is_electroacoustic=1", "ordering": 1},
                            {"name": "Dreadnought", "slug": "guitarras-acusticas-dreadnought", "params": "body_shape=dreadnought", "ordering": 2},
                        ],
                    },
                    {
                        "name": "Bajos Eléctricos",
                        "slug": "bajos-electricos",
                        "ordering": 3,
                        "subcategories": [
                            {"name": "5 cuerdas", "slug": "bajos-5-cuerdas", "params": "strings=5", "ordering": 1},
                            {"name": "Activos", "slug": "bajos-activos", "params": "circuit=active", "ordering": 2},
                            {"name": "Jazz Bass", "slug": "bajos-jazz-bass", "params": "body_shape=jazz_bass", "ordering": 3},
                            {"name": "Precision Bass", "slug": "bajos-precision-bass", "params": "body_shape=precision_bass", "ordering": 4},
                        ],
                    },
                    {"name": "Guitarras Clásicas", "slug": "guitarras-clasicas", "ordering": 4},
                    {"name": "Violines", "slug": "violines", "ordering": 5},
                    {"name": "Ukeleles", "slug": "ukeleles", "ordering": 6},
                ],
            },
            {
                "name": "Aire",
                "slug": "aire",
                "ordering": 2,
                "categories": [
                    {"name": "Flautas Traversas", "slug": "flautas-traversas", "ordering": 1},
                    {"name": "Saxofones", "slug": "saxofones", "ordering": 2},
                    {"name": "Trompetas", "slug": "trompetas", "ordering": 3},
                    {"name": "Clarinetes", "slug": "clarinetes", "ordering": 4},
                    {"name": "Armónicas", "slug": "armonicas", "ordering": 5},
                ],
            },
            {
                "name": "Percusión",
                "slug": "percusion",
                "ordering": 3,
                "categories": [
                    {"name": "Baterías Acústicas", "slug": "baterias-acusticas", "ordering": 1},
                    {"name": "Baterías Electrónicas", "slug": "baterias-electronicas", "ordering": 2},
                    {"name": "Cajas y Redoblantes", "slug": "cajas-y-redoblantes", "ordering": 3},
                    {"name": "Platillos", "slug": "platillos", "ordering": 4},
                    {"name": "Percusión Latina", "slug": "percusion-latina", "ordering": 5},
                ],
            },
            {
                "name": "Teclas",
                "slug": "teclas",
                "ordering": 4,
                "categories": [
                    {
                        "name": "Pianos Digitales",
                        "slug": "pianos-digitales",
                        "ordering": 1,
                        "subcategories": [
                            {"name": "88 Teclas con Acción de Martillo", "slug": "pianos-88-teclas-hammer", "params": "keys=88&action=hammer", "ordering": 1},
                        ],
                    },
                    {"name": "Sintetizadores", "slug": "sintetizadores", "ordering": 2},
                    {"name": "Teclados Controladores MIDI", "slug": "teclados-controladores-midi", "ordering": 3},
                ],
            },
        ],
    },
    {
        "name": "Categorías en Equipos de Sonido",
        "slug": "equipos-de-sonido",
        "ordering": 2,
        "groups": [
            {
                "name": "Amplificación",
                "slug": "amplificacion",
                "ordering": 1,
                "categories": [
                    {
                        "name": "Amplificadores de Guitarra",
                        "slug": "amplificadores-de-guitarra",
                        "ordering": 1,
                        "subcategories": [
                            {"name": "Valvulares (Tubes)", "slug": "amplis-guitarra-valvulares", "params": "tech=tubes", "ordering": 1},
                            {"name": "Digitales / Modelado", "slug": "amplis-guitarra-digitales", "params": "tech=digital", "ordering": 2},
                            {"name": "Combos", "slug": "amplis-guitarra-combos", "params": "format=combo", "ordering": 3},
                            {"name": "Cabezales", "slug": "amplis-guitarra-cabezales", "params": "format=head", "ordering": 4},
                        ],
                    },
                    {"name": "Amplificadores de Bajo", "slug": "amplificadores-de-bajo", "ordering": 2},
                    {"name": "Cabezales y Cajas", "slug": "cabezales-y-cajas", "ordering": 3},
                ],
            },
            {
                "name": "Efectos",
                "slug": "efectos",
                "ordering": 2,
                "categories": [
                    {
                        "name": "Pedales de Efectos",
                        "slug": "pedales-de-efectos",
                        "ordering": 1,
                        "subcategories": [
                            {"name": "Overdrive & Distorsión", "slug": "pedales-overdrive-distorsion", "params": "effect=overdrive,distortion", "ordering": 1},
                            {"name": "Delay & Reverb", "slug": "pedales-delay-reverb", "params": "effect=delay,reverb", "ordering": 2},
                            {"name": "Modulación", "slug": "pedales-modulacion", "params": "effect=chorus,phaser,flanger", "ordering": 3},
                        ],
                    },
                    {"name": "Pedaleras Multiefectos", "slug": "pedaleras-multiefectos", "ordering": 2},
                    {"name": "Preamps", "slug": "preamps", "ordering": 3},
                ],
            },
            {
                "name": "Grabación y Estudio",
                "slug": "grabacion-y-estudio",
                "ordering": 3,
                "categories": [
                    {
                        "name": "Interfaces de Audio",
                        "slug": "interfaces-de-audio",
                        "ordering": 1,
                        "subcategories": [
                            {"name": "2 Canales / USB", "slug": "interfaces-2-canales", "params": "inputs=2", "ordering": 1},
                            {"name": "4 o más canales", "slug": "interfaces-multicanal", "params": "inputs_min=4", "ordering": 2},
                        ],
                    },
                    {
                        "name": "Micrófonos de Estudio",
                        "slug": "microfonos-de-estudio",
                        "ordering": 2,
                        "subcategories": [
                            {"name": "Condensador", "slug": "microfonos-condensador", "params": "transducer=condenser", "ordering": 1},
                            {"name": "Dinámicos", "slug": "microfonos-dinamicos", "params": "transducer=dynamic", "ordering": 2},
                        ],
                    },
                    {"name": "Monitores de Audio", "slug": "monitores-de-audio", "ordering": 3},
                    {"name": "Audífonos de Monitoreo", "slug": "audifonos-de-monitoreo", "ordering": 4},
                ],
            },
            {
                "name": "En Vivo y PA",
                "slug": "en-vivo-y-pa",
                "ordering": 4,
                "categories": [
                    {"name": "Parlantes Activos / PA", "slug": "parlantes-activos-pa", "ordering": 1},
                    {"name": "Consolas y Mezcladoras", "slug": "consolas-y-mezcladoras", "ordering": 2},
                    {"name": "Cables y Conectores", "slug": "cables-y-conectores", "ordering": 3},
                ],
            },
        ],
    },
    {
        "name": "Categorías en Piezas y Repuestos",
        "slug": "piezas-y-repuestos",
        "ordering": 3,
        "groups": [
            {
                "name": "Cuerdas y Afinación",
                "slug": "cuerdas-y-afinacion",
                "ordering": 1,
                "categories": [
                    {"name": "Cuerdas Guitarra y Bajo", "slug": "cuerdas-guitarra-y-bajo", "ordering": 1},
                    {"name": "Clavijeros y Afinadores", "slug": "clavijeros-y-afinadores", "ordering": 2},
                    {"name": "Puentes y Cejuelas", "slug": "puentes-y-cejuelas", "ordering": 3},
                ],
            },
            {
                "name": "Electrónica y Pastillas",
                "slug": "electronica-y-pastillas",
                "ordering": 2,
                "categories": [
                    {"name": "Pastillas / Cápsulas", "slug": "pastillas-capsulas", "ordering": 1},
                    {"name": "Potenciómetros y Switches", "slug": "potenciometros-y-switches", "ordering": 2},
                    {"name": "Jacks y Placas", "slug": "jacks-y-placas", "ordering": 3},
                ],
            },
            {
                "name": "Accesorios",
                "slug": "accesorios",
                "ordering": 3,
                "categories": [
                    {"name": "Correas / Straps", "slug": "correas-straps", "ordering": 1},
                    {"name": "Fundas y Estuches", "slug": "fundas-y-estuches", "ordering": 2},
                    {"name": "Soportes / Stands", "slug": "soportes-stands", "ordering": 3},
                    {"name": "Picks / Uñetas", "slug": "picks-unetas", "ordering": 4},
                ],
            },
            {
                "name": "Mantenimiento",
                "slug": "mantenimiento",
                "ordering": 4,
                "categories": [
                    {"name": "Kits de Limpieza", "slug": "kits-de-limpieza", "ordering": 1},
                    {"name": "Aceites para Diapasón", "slug": "aceites-para-diapason", "ordering": 2},
                    {"name": "Herramientas de Calibración", "slug": "herramientas-de-calibracion", "ordering": 3},
                ],
            },
        ],
    },
]


def seed_taxonomy(session: Session) -> Dict[str, int]:
    """Populates the database with Sections, CategoryGroups, Categories, and Subcategories."""
    stats = {"sections": 0, "groups": 0, "categories": 0, "subcategories": 0}

    for s_data in TAXONOMY_FIXTURES:
        section = session.query(Section).filter(Section.slug == s_data["slug"]).first()
        if not section:
            section = Section(name=s_data["name"], slug=s_data["slug"], ordering=s_data["ordering"])
            session.add(section)
            session.flush()
            stats["sections"] += 1

        for g_data in s_data.get("groups", []):
            group = session.query(CategoryGroup).filter(CategoryGroup.slug == g_data["slug"]).first()
            if not group:
                group = CategoryGroup(
                    section_id=section.id,
                    name=g_data["name"],
                    slug=g_data["slug"],
                    ordering=g_data["ordering"],
                )
                session.add(group)
                session.flush()
                stats["groups"] += 1

            for c_data in g_data.get("categories", []):
                category = session.query(Category).filter(Category.slug == c_data["slug"]).first()
                if not category:
                    category = Category(
                        group_id=group.id,
                        name=c_data["name"],
                        slug=c_data["slug"],
                        ordering=c_data["ordering"],
                        short_description_template=c_data.get("short_description_template"),
                        browse_result_template=c_data.get("browse_result_template"),
                    )
                    session.add(category)
                    session.flush()
                    stats["categories"] += 1

                for sub_data in c_data.get("subcategories", []):
                    subcat = session.query(Subcategory).filter(Subcategory.slug == sub_data["slug"]).first()
                    if not subcat:
                        subcat = Subcategory(
                            category_id=category.id,
                            name=sub_data["name"],
                            slug=sub_data["slug"],
                            params=sub_data["params"],
                            ordering=sub_data.get("ordering", 0),
                        )
                        session.add(subcat)
                        stats["subcategories"] += 1

    session.commit()
    return stats
