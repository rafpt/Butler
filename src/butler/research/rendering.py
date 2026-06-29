"""Deterministic Portuguese Markdown rendering."""

from __future__ import annotations

from collections import Counter

from butler.core.research import RadarReport, RadarSection, RankedItem

SECTION_TITLES = {
    RadarSection.MUST: "Must",
    RadarSection.WORTH: "Worth",
    RadarSection.MONITOR: "Monitor",
    RadarSection.GOVERNANCE: "Governance",
    RadarSection.LEARNING: "Continuous Learning",
    RadarSection.IGNORED: "Ignored Noise",
}


def _truncate(value: str, limit: int = 900) -> str:
    if len(value) <= limit:
        return value
    shortened = value[:limit].rsplit(" ", 1)[0]
    return f"{shortened}…"


def _render_item(ranked: RankedItem) -> str:
    item = ranked.item
    published = item.published_at.astimezone().strftime("%Y-%m-%d %H:%M %Z")
    rationale = "; ".join(ranked.rationale)
    tags = ", ".join(item.tags[:8])
    lines = [
        f"### [{item.title}]({item.url})",
        "",
        _truncate(item.summary) or "Sem resumo disponível; consultar a fonte primária.",
        "",
        (
            f"- **Score:** {ranked.score:.2f} · **Fonte:** `{item.source_id}` "
            f"· **Publicado:** {published}"
        ),
        f"- **Racional:** {rationale}",
    ]
    if item.identifier:
        lines.append(f"- **Identificador:** `{item.identifier}`")
    if tags:
        lines.append(f"- **Tags:** {tags}")
    lines.append(f"- **Item Butler:** `{item.id}`")
    return "\n".join(lines)


def render_report(report: RadarReport) -> str:
    failures = [run for run in report.source_runs if run.status != "success"]
    counts = Counter(item.section for item in report.items)
    status = "DEGRADADO" if report.degraded else "OK"
    lines = [
        f"# Butler Cyber Radar — {report.report_date.isoformat()}",
        "",
        f"> Estado: **{status}** · Must: **{report.must_count}** · Modelo: "
        f"`{report.model or 'determinístico'}`",
        "",
        "## Síntese executiva",
        "",
        report.synthesis
        or "A síntese por modelo não ficou disponível; a priorização abaixo é determinística.",
        "",
        "## Cobertura",
        "",
        f"- Fontes consultadas: {len(report.source_runs)}",
        f"- Fontes com falha: {len(failures)}",
        f"- Itens classificados: {len(report.items)}",
    ]
    if failures:
        lines.extend(
            [
                "",
                "**Falhas parciais:** "
                + "; ".join(
                    f"`{run.source_id}` — {' '.join(run.error.split())[:160]}" for run in failures
                ),
            ]
        )

    for section in RadarSection:
        section_items = [item for item in report.items if item.section is section]
        lines.extend(
            [
                "",
                f"## {SECTION_TITLES[section]} ({counts[section]})",
                "",
            ]
        )
        if not section_items:
            lines.append("_Sem itens nesta secção._")
            continue
        max_items = 5 if section is RadarSection.IGNORED else 12
        lines.append("\n\n".join(_render_item(item) for item in section_items[:max_items]))

    lines.extend(
        [
            "",
            "## Estado das fontes",
            "",
            "| Fonte | Estado | Recebidos | Aceites | Duração |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for run in sorted(report.source_runs, key=lambda value: value.source_id):
        lines.append(
            f"| `{run.source_id}` | {run.status} | {run.received} | "
            f"{run.accepted} | {run.duration_ms} ms |"
        )
    lines.extend(
        [
            "",
            "---",
            "",
            (
                f"Gerado localmente em `{report.created_at.isoformat()}`. "
                "Conteúdo externo é tratado como não confiável; seguir sempre as fontes primárias."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def explain_item(ranked: RankedItem) -> str:
    return "\n".join(
        [
            f"# {ranked.item.title}",
            "",
            f"- Item: `{ranked.item.id}`",
            f"- Secção: `{ranked.section.value}`",
            f"- Score: `{ranked.score:.4f}`",
            f"- Fonte: [{ranked.item.source_id}]({ranked.item.url})",
            f"- Publicado: `{ranked.item.published_at.isoformat()}`",
            f"- Racional: {'; '.join(ranked.rationale)}",
            f"- Watchlist: {', '.join(ranked.watch_matches) or 'sem correspondências'}",
            "",
            ranked.item.summary,
        ]
    )
