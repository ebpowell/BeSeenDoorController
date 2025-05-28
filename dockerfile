# Stage 1: Builder
FROM python:3.9-slim-buster as builder

WORKDIR /app

# Install build dependencies if needed (e.g., for packages with C extensions)
# RUN apt-get update && apt-get install -y build-essential --no-install-recommends && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source code for the build stage
COPY . .

# You might also build wheels here for your local packages
RUN python setup.py bdist_wheel


# Stage 2: Production runtime
FROM python:3.9-slim-buster

WORKDIR /app

# Copy only the installed dependencies from the builder stage's virtual environment
# or just rely on pip install in the final stage if not using a venv strategy
# For setuptools package, we often just reinstall in the final stage.

# If you built wheels in the builder stage:
COPY --from=builder /app/dist/*.whl .
RUN pip install --no-cache-dir *.whl

# For a simple setup tools package, copy the project and install again
# or carefully copy specific installed files (more complex)
# COPY --from=builder /app/ww_door_controller /app/ww_door_controller
# RUN pip install --no-cache-dir /app/ww_door_controller

# Create a non-root user for security
RUN adduser --system --group doorcontroller
USER doorcontroller

# Expose the port your application listens on
EXPOSE 8000

# Command to run your application
CMD ["get_recent_swipes.py", "DockerUser"] # Assuming my_script.py is on PATH