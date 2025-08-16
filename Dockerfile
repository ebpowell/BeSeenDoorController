# Stage 1: Builder
FROM python:3.10-slim-buster AS builder

#  Set environment variables for Python in the container
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Install build dependencies if needed (e.g., for packages with C extensions)
# RUN apt-get update && apt-get install -y build-essential --no-install-recommends && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache/pip

# Copy your entire Python package source code and setup.py
# This includes door_controller/ and setup.py
COPY door_controller /app/door_controller
COPY setup.py /app/setup.py

# Install your package using setuptools
# This command will install the package and make its 'console_scripts' available
# in the container's PATH (typically /usr/local/bin)
RUN pip install --no-cache-dir .

# Stage 2: Production Runtime (minimal image for deployment)
# Start from a clean, slim Python base image again
FROM python:3.10-slim-buster

# Set environment variables again for the runtime stage
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy only the installed dependencies from the builder stage's virtual environment
# or just rely on pip install in the final stage if not using a venv strategy
# For setuptools package, we often just reinstall in the final stage.

# For a simple setup tools package, copy the project and install again
# or carefully copy specific installed files (more complex)
# COPY --from=builder /app/ww_door_controller /app/ww_door_controller
# RUN pip install --no-cache-dir /app/ww_door_controller

# Create a non-root user for security
RUN adduser --system --group doorcontroller && \
    mkdir -p /app/data /app/config /app/logs && \
    chown -R doorcontroller:doorcontroller /app
# Switch to the non-root user
USER doorcontroller

COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
# Copy each console script individually
COPY --from=builder /usr/local/bin/get_swipes /usr/local/bin/
COPY --from=builder /usr/local/bin/get_acl_from_controller /usr/local/bin/
COPY --from=builder /usr/local/bin/get_foblist_from_controller /usr/local/bin/
# Expose the port your application listens on
# EXPOSE 8000

# Command to run your application
# Define a default command if the container is run without arguments
# This is mainly for user guidance or a simple health check
CMD ["echo", "Ready. Run with: docker run door_controller get_recent_swipes [args], docker run get_acl_from_controller [args], or docker run get_foblist_from_controller [args]"]
# CMD ["get_recent_swipes.py", "DockerUser"] # Assuming my_script.py is on PATH
