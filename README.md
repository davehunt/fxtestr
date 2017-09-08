# Firefox Test Results

[Flask](http://flask.pocoo.org/) app for presenting Firefox test results
from [ActiveData](https://wiki.mozilla.org/Auto-tools/Projects/ActiveData).

![bd979230-bd0f-4422-8441-2610d27258b6](https://user-images.githubusercontent.com/122800/30221878-ceab8aac-94bc-11e7-9d6a-30fdb2f95d96.png)

To build and run you will need [Docker](https://www.docker.com/) installed:

```sh
$ docker build -t fxtestr .
$ docker run -d  -p 80:80 fxtestr
```

The Docker image is based on [uwsgi-nginx-flask](https://hub.docker.com/r/tiangolo/uwsgi-nginx-flask/),
where you can find more details on building and running the image.
