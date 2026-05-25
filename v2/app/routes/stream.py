"""Server-Sent Events streaming endpoint para lançar uma campanha com feedback live.

Frontend usa EventSource e recebe eventos enquanto o pipeline corre.
"""

import asyncio
import json

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from loguru import logger

from ..database import SessionLocal
from ..deps import require_user
from ..models import Campaign
from ..services.pipeline import capture, send_campaign


router = APIRouter(prefix="/api", tags=["stream"])


def _format_event(payload: dict) -> str:
    """Encoda um evento SSE no formato `event: NAME\\ndata: JSON\\n\\n`."""
    event = payload.pop("event", "message")
    data = json.dumps(payload, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {data}\n\n"


@router.get("/campaigns/{campaign_id}/stream")
async def stream_campaign(campaign_id: int, request: Request, user: str = Depends(require_user)):
    """Executa o pipeline de captura + envio da campanha emitindo eventos SSE.

    O cliente faz `new EventSource('/api/campaigns/123/stream')`.
    """

    # Validate campaign exists in a quick session.
    db_check = SessionLocal()
    try:
        campaign = db_check.get(Campaign, campaign_id)
        if not campaign:
            db_check.close()
            raise HTTPException(404, "Campanha não encontrada")
        # Capture all relevant fields out so we can close this session
        c_id = campaign.id
        c_niche = campaign.niche
        c_city = campaign.city
        c_max_leads = (campaign.max_leads or 60) if hasattr(campaign, "max_leads") else 60
        c_expand = (campaign.expand_variations if hasattr(campaign, "expand_variations") else True)
    finally:
        db_check.close()

    async def event_generator():
        # Queue para passar eventos do worker async para o generator
        queue: asyncio.Queue = asyncio.Queue()
        finished = asyncio.Event()

        async def emit(ev: dict):
            await queue.put(ev)

        async def worker():
            db = SessionLocal()
            try:
                await emit({"event": "start", "campaign_id": c_id, "niche": c_niche, "city": c_city, "max_leads": c_max_leads})
                captured = await capture(
                    db, c_niche, c_city,
                    max_leads=c_max_leads,
                    expand_variations=c_expand,
                    campaign_id=c_id,
                    on_event=emit,
                )
                if captured > 0:
                    await emit({"event": "step", "label": "A enviar mensagens...", "progress": 96})
                    result = await send_campaign(db, c_id, on_event=emit)
                    await emit({
                        "event": "done",
                        "captured": captured,
                        "sent_whatsapp": result.get("sent_whatsapp", 0),
                        "sent_email": result.get("sent_email", 0),
                        "errors": result.get("errors", 0),
                        "progress": 100,
                    })
                else:
                    await emit({"event": "done", "captured": 0, "progress": 100, "message": "Nenhum lead novo capturado"})
            except Exception as e:
                logger.exception("stream worker failed: {}", e)
                await emit({"event": "error", "message": str(e)[:300]})
            finally:
                db.close()
                finished.set()

        worker_task = asyncio.create_task(worker())

        try:
            # Heartbeat inicial
            yield ":ok\n\n"

            while True:
                # Cliente desconectou?
                if await request.is_disconnected():
                    worker_task.cancel()
                    break

                # Esperar evento OU heartbeat de 10s
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=10.0)
                    yield _format_event(ev)
                    if ev.get("event") in ("done", "error"):
                        # Drenar fila final
                        while not queue.empty():
                            yield _format_event(queue.get_nowait())
                        break
                except asyncio.TimeoutError:
                    yield ":heartbeat\n\n"
                    if finished.is_set() and queue.empty():
                        break
        finally:
            if not worker_task.done():
                worker_task.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # disable nginx buffering if any
            "Connection": "keep-alive",
        },
    )
