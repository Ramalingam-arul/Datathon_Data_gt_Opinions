# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Run Streamlit, utilizing Catalyst's dynamic port environment variable
CMD sh -c "streamlit run app.py --server.port=${X_ZOHO_CATALYST_LISTEN_PORT:-8080} --server.address=0.0.0.0"