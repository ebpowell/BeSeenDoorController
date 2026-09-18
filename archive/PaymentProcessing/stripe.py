import os
import stripe
from flask import Flask, jsonify, request

app = Flask(__name__)

# Load secret key from environment variables (use test key sk_test_... in dev)
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

def calculate_order_amount(items):
    """
    Always calculate totals on the server to prevent price tampering.
    Stripe expects amounts in the smallest currency unit (e.g., cents for USD).
    """
    # Example fixed calculation: $20.00 = 2000 cents
    return 2000

@app.route("/create-payment-intent", methods=["POST"])
def create_payment():
    try:
        data = request.get_json() or {}
        items = data.get("items", [])

        # 1. Create a PaymentIntent with the order amount and currency
        intent = stripe.PaymentIntent.create(
            amount=calculate_order_amount(items),
            currency="usd",
            # Automatically detect and enable supported payment methods (Cards, Apple Pay, etc.)
            automatic_payment_methods={"enabled": True},
            metadata={"order_id": "ORDER_12345"},
        )

        # 2. Send the client secret back to the frontend
        return jsonify({"clientSecret": intent.client_secret}), 200

    except stripe.error.CardError as e:
        # A declined card or incorrect details
        err = e.error
        return jsonify({"error": err.message, "code": err.code}), 400

    except stripe.error.RateLimitError:
        return jsonify({"error": "Too many requests to Stripe API"}), 429

    except stripe.error.InvalidRequestError as e:
        return jsonify({"error": f"Invalid parameters: {e}"}), 400

    except stripe.error.AuthenticationError:
        return jsonify({"error": "Authentication with Stripe failed"}), 401

    except stripe.error.APIConnectionError:
        return jsonify({"error": "Network communication failed"}), 503

    except stripe.error.StripeError as e:
        return jsonify({"error": f"Stripe processing error: {e.user_message}"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(port=4242, debug=True)