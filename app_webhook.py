"""Stripe Webhook endpoint - FastAPI."""
from fastapi import FastAPI, Request, Header, HTTPException
import stripe
from config_dir import AppConfig
from services.billing_service import handle_webhook_event

_config = AppConfig()
stripe.api_key = _config.stripe.secret_key

app = FastAPI(title="BidIntel Webhook", version="1.0.0")


@app.post("/webhook/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    """Handle Stripe webhook events."""
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, _config.stripe.webhook_secret
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="Invalid signature")

    handle_webhook_event(event)
    return {"status": "ok"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)