FROM public.ecr.aws/lambda/python:3.12

# Install git using dnf (https://docs.aws.amazon.com/lambda/latest/dg/python-image.html#python-image-base)
# For python 3.12, dnf replaces yum for package management
RUN dnf install git -y

# run a pip install for poetry 1.5.0
RUN pip install poetry==1.5.0

# Copy the poetry.lock and pyproject.toml files
COPY pyproject.toml poetry.lock ${LAMBDA_TASK_ROOT}/

# Install the dependencies
WORKDIR ${LAMBDA_TASK_ROOT}
RUN poetry config virtualenvs.create false
RUN poetry install --only main

# Copy config folder
COPY config ${LAMBDA_TASK_ROOT}/config

# Copy function code
COPY src/main.py ${LAMBDA_TASK_ROOT}/src/
COPY src/logger.py ${LAMBDA_TASK_ROOT}/src/

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD [ "src.main.handler" ]