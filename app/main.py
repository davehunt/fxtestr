from datetime import datetime
import os
import re

from bokeh.embed import components
from bokeh.layouts import row
from bokeh.plotting import figure
from flask import Flask, redirect, render_template, request, url_for
from flask_caching import Cache
import numpy as np
import pandas as pd
import requests

cache = Cache(config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': '.cache'})
app = Flask(__name__)
app.config.from_object(__name__)
cache.init_app(app)


class ActiveData(object):

    def __init__(self, request, path):
        self.request = request
        self.path = path

    @staticmethod
    @cache.memoize(timeout=3600)
    def _query(query):
        url = 'http://activedata.allizom.org/query'
        print(query)
        r = requests.post(url, data=query).json()
        meta = r['meta']
        meta['timestamp'] = datetime.now()
        print(meta)
        data = pd.DataFrame(r['data'], columns=r['header'])
        print(data)
        return r['meta'], data

    def query(self, name):
        path = os.path.join(self.path, name + '.json')
        template_vars = request.form.to_dict()
        template_vars.setdefault('since', 'today-1week')
        return self._query(render_template(path, **template_vars))

    @property
    def summary(self):
        meta, data = self.query('summary')
        data['start'] = pd.to_datetime(data['start'], unit='s')
        data['end'] = pd.to_datetime(data['end'], unit='s')
        return meta, data

    @property
    def tests_by_date(self):
        data = self.query('tests_by_date')[1]
        data['date'] = pd.to_datetime(data['date'], unit='s')
        data['distinct'].fillna(0, inplace=True)
        data.sort_values(by='date', inplace=True)
        return data.set_index('date')

    @property
    def failures_by_date(self):
        data = self.query('failures_by_date')[1]
        data['date'] = pd.to_datetime(data['date'], unit='s')
        data['distinct'].fillna(0, inplace=True)
        data.sort_values(by='date', inplace=True)
        return data.set_index('date')

    @property
    def failures(self):
        meta, data = self.query('failures')
        data['pass'] = 1 - data['failures']/data['total']
        return meta, data[data.failures > 0].sort_values('pass')[:5]

    @property
    def skipped(self):
        meta, data = self.query('skipped')
        data['concentration'] = data['skips']/data['total']
        data = data[data.skips > 0].sort_values('skips', ascending=False)
        return meta, data[:5]

    @property
    def slowest(self):
        meta, data = self.query('durations')
        return meta, data.sort_values('duration', ascending=False)[:5]

    @property
    def xfails(self):
        meta, data = self.query('xfails')
        return meta, data[:5]

    @property
    def tests_failures(self):
        meta, data = self.query('tests_failures')
        data['id'] = data.id.apply(lambda x: re.sub(r'\W', '', x))
        data['date'] = pd.to_datetime(data['date'], unit='s')
        return meta, data.sort_values(by='date', ascending=False)[:50]

    @property
    def tests_skipped(self):
        meta, data = self.query('tests_skipped')
        data['id'] = data.id.apply(lambda x: re.sub(r'\W', '', x))
        data['date'] = pd.to_datetime(data['date'], unit='s')
        return meta, data.sort_values(by='date', ascending=False)[:50]

    @property
    def tests_slowest(self):
        meta, data = self.query('tests')
        data['id'] = data.id.apply(lambda x: re.sub(r'\W', '', x))
        data['date'] = pd.to_datetime(data['date'], unit='s')
        return meta, data.sort_values(by='duration', ascending=False)[:50]

    @property
    def tests_xfails(self):
        meta, data = self.query('tests_xfails')
        data['id'] = data.id.apply(lambda x: re.sub(r'\W', '', x))
        data['date'] = pd.to_datetime(data['date'], unit='s')
        return meta, data.sort_values(by='date', ascending=False)[:50]


@app.route('/')
def index():
    return redirect(url_for('fxtest'))


@app.route('/fx-test')
def fxtest():
    return render_template(os.path.join('fx-test', 'index.html'))


@app.route('/fx-test/filters', methods=['POST'])
def fxtest_filters():
    ad = ActiveData(request, 'fx-test')
    filters = [
        {'id': 'project',
         'label': 'Project',
         'options': sorted(ad.query('projects')[1].job.apply(
             lambda x: x.partition('.')[0]).unique().tolist()),
         'selected': request.form.get('project', '')},
        {'id': 'job',
         'label': 'Job',
         'options': sorted(ad.query('jobs')[1].job.tolist()),
         'selected': request.form.get('job', '')},
        {'id': 'since',
         'label': 'Since',
         'options': [
            'today-1week',
            'today-2week',
            'today-4week',
            'today-8week',
            'today-16week'],
         'selected': request.form.get('since', 'today-1week')}]
    return render_template('filters.html', filters=filters)


@app.route('/fx-test/summary', methods=['POST'])
def fxtest_summary():
    meta, data = ActiveData(request, 'fx-test').summary
    template_vars = {
        'meta': meta,
        'distinct': '{:,}'.format(data.distinct[0]),
        'total': '{:,}'.format(data.total[0]),
        'start': data.start[0].strftime('%d-%b-%Y'),
        'end': data.end[0].strftime('%d-%b-%Y')}
    return render_template('summary.html', **template_vars)


@app.route('/fx-test/plot', methods=['POST'])
def fxtest_plot():
    ad = ActiveData(request, 'fx-test')
    tests = ad.tests_by_date
    failures = ad.failures_by_date
    return plot(tests, failures)


@app.route('/fx-test/failures', methods=['POST'])
def fxtest_failures():
    meta, data = ActiveData(request, 'fx-test').failures
    template_vars = {'meta': meta, 'tests': data.to_dict(orient='records')}
    return render_template('failures.html', **template_vars)


@app.route('/fx-test/skipped', methods=['POST'])
def fxtest_skipped():
    meta, data = ActiveData(request, 'fx-test').skipped
    template_vars = {'meta': meta, 'tests': data.to_dict(orient='records')}
    return render_template('skipped.html', **template_vars)


@app.route('/fx-test/slowest', methods=['POST'])
def fxtest_slowest():
    meta, data = ActiveData(request, 'fx-test').slowest
    template_vars = {'meta': meta, 'tests': data.to_dict(orient='records')}
    return render_template('slowest.html', **template_vars)


@app.route('/fx-test/xfails', methods=['POST'])
def fxtest_xfails():
    meta, data = ActiveData(request, 'fx-test').xfails
    template_vars = {'meta': meta, 'tests': data.to_dict(orient='records')}
    return render_template('xfails.html', **template_vars)


@app.route('/fx-test/tests/failures', methods=['POST'])
def fxtest_tests_failures():
    meta, data = ActiveData(request, 'fx-test').tests_failures
    template_vars = {'meta': meta, 'tests': data.to_dict(orient='records')}
    return render_template('tests.html', **template_vars)


@app.route('/fx-test/tests/skipped', methods=['POST'])
def fxtest_tests_skipped():
    meta, data = ActiveData(request, 'fx-test').tests_skipped
    template_vars = {'meta': meta, 'tests': data.to_dict(orient='records')}
    return render_template('tests.html', **template_vars)


@app.route('/fx-test/tests/slowest', methods=['POST'])
def fxtest_tests_slowest():
    meta, data = ActiveData(request, 'fx-test').tests_slowest
    template_vars = {'meta': meta, 'tests': data.to_dict(orient='records')}
    return render_template('tests.html', **template_vars)


@app.route('/fx-test/tests/xfails', methods=['POST'])
def fxtest_tests_xfails():
    meta, data = ActiveData(request, 'fx-test').tests_xfails
    template_vars = {'meta': meta, 'tests': data.to_dict(orient='records')}
    return render_template('tests.html', **template_vars)


@app.route('/unittest')
def unittest():
    return render_template(os.path.join('unittest', 'index.html'))


@app.route('/unittest/filters', methods=['POST'])
def unittest_filters():
    filters = [
        {'id': 'branch',
         'label': 'Branch',
         'options': ['autoland', 'mozilla-inboud', 'mozilla-central', 'mozilla-beta'],
         'selected': request.form.get('branch', 'autoland')},
        {'id': 'path',
         'label': 'Path',
         'value': request.form.get('path', '')},
        {'id': 'since',
         'label': 'Since',
         'options': [
            'today-1week',
            'today-2week',
            'today-4week',
            'today-8week',
            'today-16week'],
         'selected': request.form.get('since', 'today-1week')}]
    return render_template('filters.html', filters=filters)


@app.route('/unittest/summary', methods=['POST'])
def unittest_summary():
    meta, data = ActiveData(request, 'unittest').summary
    template_vars = {
        'meta': meta,
        'distinct': '{:,}'.format(data.distinct[0]),
        'total': '{:,}'.format(data.total[0]),
        'start': data.start[0].strftime('%d-%b-%Y'),
        'end': data.end[0].strftime('%d-%b-%Y')}
    return render_template('summary.html', **template_vars)


@app.route('/unittest/plot', methods=['POST'])
def unittest_plot():
    ad = ActiveData(request, 'unittest')
    tests = ad.tests_by_date
    failures = ad.failures_by_date
    return plot(tests, failures)


@app.route('/unittest/failures', methods=['POST'])
def unittest_failures():
    meta, data = ActiveData(request, 'unittest').failures
    template_vars = {'meta': meta, 'tests': data.to_dict(orient='records')}
    return render_template('failures.html', **template_vars)


@app.route('/unittest/skipped', methods=['POST'])
def unittest_skipped():
    meta, data = ActiveData(request, 'unittest').skipped
    template_vars = {'meta': meta, 'tests': data.to_dict(orient='records')}
    return render_template('skipped.html', **template_vars)


@app.route('/unittest/slowest', methods=['POST'])
def unittest_slowest():
    meta, data = ActiveData(request, 'unittest').slowest
    template_vars = {'meta': meta, 'tests': data.to_dict(orient='records')}
    return render_template('slowest.html', **template_vars)


@app.route('/unittest/xfails', methods=['POST'])
def unittest_xfails():
    meta, data = ActiveData(request, 'unittest').xfails
    template_vars = {'meta': meta, 'tests': data.to_dict(orient='records')}
    return render_template('xfails.html', **template_vars)


@app.route('/unittest/tests/failures', methods=['POST'])
def unittest_tests_failures():
    meta, data = ActiveData(request, 'unittest').tests_failures
    template_vars = {'meta': meta, 'tests': data.to_dict(orient='records')}
    return render_template('tests.html', **template_vars)


@app.route('/unittest/tests/skipped', methods=['POST'])
def unittest_tests_skipped():
    meta, data = ActiveData(request, 'unittest').tests_skipped
    template_vars = {'meta': meta, 'tests': data.to_dict(orient='records')}
    return render_template('tests.html', **template_vars)


@app.route('/unittest/tests/slowest', methods=['POST'])
def unittest_tests_slowest():
    meta, data = ActiveData(request, 'unittest').tests_slowest
    template_vars = {'meta': meta, 'tests': data.to_dict(orient='records')}
    return render_template('tests.html', **template_vars)


@app.route('/unittest/tests/xfails', methods=['POST'])
def unittest_tests_xfails():
    meta, data = ActiveData(request, 'unittest').tests_xfails
    template_vars = {'meta': meta, 'tests': data.to_dict(orient='records')}
    return render_template('tests.html', **template_vars)


def plot(tests, failures):
    tools = 'pan,wheel_zoom,box_zoom,save,reset'
    df = pd.concat([tests, failures], axis=1, keys=['tests', 'failures'])
    x = np.concatenate((df.index, df.index[::-1]))

    x_range = (df.index.min().timestamp() * 1000,
               df.index.max().timestamp() * 1000)
    p1 = figure(title='Distinct Tests', toolbar_location='above', tools=tools,
                plot_height=250, plot_width=450, x_axis_type='datetime',
                x_range=x_range)
    stable = df.tests.distinct - df.failures.distinct
    y_range = df.tests.distinct.max() - stable.min() or stable.min()
    p1.toolbar.logo = None
    p1.y_range.start = max(0, stable.min() - (y_range * 0.3))
    p1.y_range.end = df.tests.distinct.max() + (y_range * 0.3)
    p1.patch(x, np.concatenate((stable, np.zeros(len(stable)))), alpha=0.6,
             line_alpha=0)
    p1.patch(x, np.concatenate((stable, df.tests.distinct[::-1])), alpha=0.6,
             fill_color='firebrick', line_alpha=0)

    p2 = figure(title='Total Failures', toolbar_location='above', tools=tools,
                plot_height=250, plot_width=450, x_axis_type='datetime',
                x_range=x_range)
    p2.toolbar.logo = None
    p2.y_range.start = 0
    p2.patch(x, np.concatenate((df.failures.total, np.zeros(len(df.tests)))),
             alpha=0.6, fill_color='firebrick', line_alpha=0)

    p3 = figure(title='Average Test Duration', toolbar_location='above',
                tools=tools, plot_height=250, plot_width=450,
                x_axis_type='datetime', x_range=x_range)
    p3.toolbar.logo = None
    p3.y_range.start = 0
    p3.patch(x, np.concatenate((df.tests.duration, np.zeros(len(df.tests)))),
             alpha=0.6, line_alpha=0)

    script, content = components(row(p1, p2, p3))
    return render_template('plot.html', script=script, content=content)


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True, port=80)
