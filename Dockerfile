FROM tiangolo/uwsgi-nginx-flask:python3.6

EXPOSE 80

COPY ./app /app

RUN pip install -r requirements.txt
