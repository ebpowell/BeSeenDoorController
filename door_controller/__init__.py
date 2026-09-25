__version__ = "0.1.0"
# In door_controller.__init__:
self.timeout = 5       # Reduce individual request timeout from 10 to 5 seconds
self.max_retries = 3   # Reduce total retries from 6 to 3

retry_strategy = Retry(
    total=self.max_retries,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    raise_on_status=False,
    allowed_methods=["GET", "POST"]
)