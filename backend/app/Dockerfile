# Stage 1: Install Chrome
FROM public.ecr.aws/lambda/python:3.9 as stage

# Install dependencies
RUN yum install -y -q sudo unzip

# Set Chromium version
ENV CHROMIUM_VERSION=1002910

# Install Chromium
COPY install-browser.sh /tmp/
RUN /usr/bin/bash /tmp/install-browser.sh

# Stage 2: Final image
FROM public.ecr.aws/lambda/python:3.9

# Install Chrome dependencies
COPY chrome-deps.txt /tmp/
RUN yum install -y $(cat /tmp/chrome-deps.txt)

# Install Python dependencies
COPY requirements.txt /tmp/
RUN python3 -m pip install --upgrade pip -q
RUN python3 -m pip install -r /tmp/requirements.txt -q

# Copy Chrome and ChromeDriver from stage 1
COPY --from=stage /opt/chrome /opt/chrome
COPY --from=stage /opt/chromedriver /opt/chromedriver

# Set up environment variables
ENV PYTHONUNBUFFERED=1

# Copy the application code
COPY . /app

# Set the working directory
WORKDIR /app

# Run the script
CMD ["python", "app.py"]