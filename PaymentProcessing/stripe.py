import os
import stripe
from flask import Flask, jsonify, request

app = Flask(__name__)

# Load secret key from environment variables (use test key sk_test_... in dev)
stripe_key = os.environ.get("STRIPE_SECRET_KEY", "sk_test_mock_key_12345")
stripe.api_key = stripe_key

def extract_owner_last_name(owner_name):
    """
    Extracts the property owner's last name from their full name.
    E.g. 'John Smith' -> 'Smith'. Defaults to 'Resident' if unspecified.
    """
    if not owner_name or not str(owner_name).strip():
        return "Resident"
    parts = str(owner_name).strip().split()
    return parts[-1] if parts else "Resident"

def generate_reservation_item_name(owner_name):
    """
    Formats the item name as 'Clubhouse Reservation - [Owner LastName]'.
    """
    last_name = extract_owner_last_name(owner_name)
    return f"Clubhouse Reservation - {last_name}"

def calculate_order_amount_cents(amount_dollars):
    """
    Converts dollar amount to cents integer for Stripe processing.
    """
    try:
        val = float(amount_dollars)
        return int(round(val * 100))
    except (ValueError, TypeError):
        return 1500  # Default $15.00 in cents

def create_swipe_payment_intent(amount_dollars, owner_name, reservation_id=None):
    """
    Creates a Stripe PaymentIntent for swipe/card processing with:
      - amount in cents calculated from WebUI total
      - description/item name formatted as 'Clubhouse Reservation - [Owner LastName]'
      - metadata containing reservation_id and owner last name
    Returns dict with success status, clientSecret, payment_intent_id, item_name, amount_cents.
    """
    item_name = generate_reservation_item_name(owner_name)
    amount_cents = calculate_order_amount_cents(amount_dollars)
    owner_last_name = extract_owner_last_name(owner_name)

    api_key = os.environ.get("STRIPE_SECRET_KEY", "")

    # If no real live/test Stripe key provided, use reliable test mode mock response
    if not api_key or api_key == "sk_test_mock_key_12345" or api_key.startswith("sk_test_mock"):
        res_id_str = str(reservation_id) if reservation_id else "new"
        mock_id = f"pi_swipe_mock_res_{res_id_str}_{amount_cents}"
        return {
            "success": True,
            "clientSecret": f"{mock_id}_secret_test",
            "payment_intent_id": mock_id,
            "item_name": item_name,
            "amount_cents": amount_cents,
            "amount_dollars": amount_cents / 100.0,
            "owner_last_name": owner_last_name,
            "is_mock": True
        }

    try:
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="usd",
            description=item_name,
            automatic_payment_methods={"enabled": True},
            metadata={
                "item_name": item_name,
                "owner_last_name": owner_last_name,
                "reservation_id": str(reservation_id) if reservation_id else "",
                "type": "clubhouse_reservation"
            },
        )
        return {
            "success": True,
            "clientSecret": intent.client_secret,
            "payment_intent_id": intent.id,
            "item_name": item_name,
            "amount_cents": amount_cents,
            "amount_dollars": amount_cents / 100.0,
            "owner_last_name": owner_last_name,
            "is_mock": False
        }
    except stripe.error.StripeError as e:
        return {
            "success": False,
            "error": getattr(e, 'user_message', str(e)),
            "item_name": item_name,
            "amount_cents": amount_cents
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "item_name": item_name,
            "amount_cents": amount_cents
        }

@app.route("/create-payment-intent", methods=["POST"])
def create_payment():
    try:
        data = request.get_json() or {}
        amount = data.get("amount", 15.00)
        owner_name = data.get("owner_name", "Resident")
        reservation_id = data.get("reservation_id")

        result = create_swipe_payment_intent(amount, owner_name, reservation_id)
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify({"error": result.get("error", "Payment Intent Creation Failed")}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(port=4242, debug=True)