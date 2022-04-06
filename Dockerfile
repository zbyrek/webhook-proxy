ARG BASE_IMAGE="alpine"

FROM $BASE_IMAGE

LABEL maintainer "zbyrek <zbyrek93@gmail.com>"

RUN apk --no-cache add python3 py-pip tzdata

ADD requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

RUN adduser -S webapp
USER webapp

ADD src /app
WORKDIR /app

ENV PYTHONUNBUFFERED=1

ENTRYPOINT [ "python3", "app.py"]

# add app info as environment variables
ARG GIT_COMMIT
ENV GIT_COMMIT $GIT_COMMIT
ARG BUILD_TIMESTAMP
ENV BUILD_TIMESTAMP $BUILD_TIMESTAMP
