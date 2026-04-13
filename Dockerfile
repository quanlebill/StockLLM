FROM python:3.13
WORKDIR /StockLLM

# Install the application dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy in the source code
COPY src ./src
EXPOSE 8080

# Setup an app user so the container doesn't run as the root user
RUN useradd StockAgent
USER StockAgent

CMD ["python", "run_all.py"]