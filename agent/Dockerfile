FROM python:3.13.12-slim

# Install the application dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy in the source code
RUN useradd agent


COPY --chown=agent:agent . /agent
WORKDIR /agent

# Setup an app user so the container doesn't run as the root user
USER agent
EXPOSE 8080
CMD ["python", "main.py"]