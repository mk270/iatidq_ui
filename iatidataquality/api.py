
#  IATI Data Quality, tools for Data QA on IATI-formatted  publications
#  by Mark Brough, Martin Keegan, Ben Webb and Jennifer Smith
#
#  Copyright (C) 2013  Publish What You Fund
#
#  This programme is free software; you may redistribute and/or modify
#  it under the terms of the GNU Affero General Public License v3.0

from flask import Flask, abort, url_for, redirect, request, current_app, make_response
from functools import wraps, update_wrapper
import json
import math

from iatidataquality import app

import os
import sys
current = os.path.dirname(os.path.abspath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

from iatidq import dqdownload, dqpackages, ui_support

import datetime
class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)

def jsonify(*args, **kwargs):
    return current_app.response_class(json.dumps(dict(*args, **kwargs),
            indent=None if request.is_xhr else 2, cls=JSONEncoder),
        mimetype='application/json')

def support_jsonp(func):
    """Wraps JSONified output for JSONP requests."""
    @wraps(func)
    def decorated_function(*args, **kwargs):
        callback = request.args.get('callback', False)
        if callback:
            data = str(func(*args, **kwargs).data)
            content = str(callback) + '(' + data + ')'
            mimetype = 'application/javascript'
            return current_app.response_class(content, mimetype=mimetype)
        else:
            return func(*args, **kwargs)
    return decorated_function

def nocache(f):
    def new_func(*args, **kwargs):
        resp = make_response(f(*args, **kwargs))
        resp.cache_control.no_cache = True
        return resp
    return update_wrapper(new_func, f)

class AggregatedTestResults:
    def make_division(self,i):
        return [i* self.divisions, (i+1) * self.divisions]
    def x_axis(self):
        return map(self.make_division, range(self.n))
    def __init__(self, n, data):
        self.n = n
        self.data = data
        self.divisions = 100.0/n
    def aggregate_data(self):
        out = [0] * self.n
        for value in self.data.values():
            if value == 100.0: out[-1] += 1
            else: out[ int(math.floor(value/(100.0/self.n))) ] += 1
        return out
    def create_report(self):
        return {"data" : self.aggregate_data(), "x_axis": self.x_axis()}

def test_percentages(data):
    packages = set(map(lambda x: x[2], data))
    d = dict(map(lambda x: ((x[2],x[1]),x[0]), data))
    out = {}
    for p in packages:
        try: fail = d[(p,0)]
        except: fail = 0
        try: success = d[(p,1)]
        except: success = 0
        out[p] =  (float(success)/(fail+success)) * 100
    return out

def test_tuples(data):
    packages = set(map(lambda x: x[2], data))
    d = dict(map(lambda x: ((x[2],x[1]),x[0]), data))
    out = {}
    for p in packages:
        try: fail = d[(p,0)]
        except: fail = 0
        try: success = d[(p,1)]
        except: success = 0
        out[p] = (success, fail+success) 
    return out

def aggregated_test_results(data):
    return AggregatedTestResults(10, test_percentages(data)).create_report()

def results_by_org(data, packages):
    tests = test_tuples(data)
    package_dict = map(lambda x: x.as_dict(), packages)
    for package in package_dict:
        try:
            package['passed'] = tests[package['id']][0]
            package['total'] = tests[package['id']][1]
        except KeyError:
            package['passed'] = 0
            package['total'] = 0
    return package_dict 

@app.route("/api/")
def api_index():
    return jsonify({"packages": url_for("api_packages"), "tests":url_for("tests")})

@app.route("/api/tests/")
def api_tests():
    data = ui_support.get_results()
    percentage_passed = test_percentages(data)

    tests = ui_support.mapped_tests()
    for test in tests:
        try:
            test["percentage_passed"] = percentage_passed[test['id']] 
        except KeyError:
            test["percentage_passed"] = ""
    return jsonify({"tests": tests})

@app.route("/api/tests/<test_id>")
def api_test(test_id):
    test = ui_support.get_test(test_id)
    if test == None:
        abort(404)
    else:
        return jsonify(test.as_dict())

@app.route("/api/packages/active/")
def api_packages_active():

    active_packages = ui_support.get_active_packages()
    
    data = [ (package.package_name, package.active)
             for package in active_packages ]

    return jsonify(data)

@app.route("/api/packages/")
@support_jsonp
def api_packages():
    packages = ui_support.all_packages()

    data = ui_support.get_package_results()

    return jsonify(
                   aggregated_test_results= aggregated_test_results(data), results_by_org=results_by_org(data, packages))

@app.route("/api/packages/run/<package_id>/")
def api_package_run(package_id):
    try:
        dqdownload.run(package_id)
        status = "ok"
    except Exception, e:
        status = "failed"
    return jsonify({"status": status})

@app.route("/api/packages/status/<package_id>/")
@nocache
def api_package_status(package_id):
    try:
        status = dqpackages.package_status(package_id)
        return jsonify(status.as_dict())
    except Exception:
        return jsonify({"status":"failed"})

@app.route('/api/packages/<package_name>')
@support_jsonp
def api_package(package_name):
    package = ui_support.get_package_by_name(package_name)
    if package == None:
        abort(404)
    else:
        return jsonify(package.as_dict())

@app.route('/api/publishers/<publisher_id>')
@support_jsonp
def api_publisher_data(publisher_id):

    import urllib2
    url = "http://staging.publishwhatyoufund.org/api/publishers/" + publisher_id

    req = urllib2.Request(url)
    try:
        response = urllib2.urlopen(req)
        the_page = response.read()
        rv = app.make_response(the_page)
        rv.mimetype = 'application/json'
        return rv
    except urllib2.HTTPError, e:
        return jsonify(e)

@app.route('/api/packages/<package_name>/hierarchy/<hierarchy_id>/tests/<test_id>/activities')
@app.route('/api/packages/<package_name>/tests/<test_id>/activities')
@support_jsonp
def api_package_activities(package_name, test_id, hierarchy_id=None):
    package = ui_support.get_package_by_name(package_name)
    latest_runtime = ui_support.latest_runtime(package)

    if (hierarchy_id):
        if (hierarchy_id=="None"): 
            hierarchy_id = None
        test_results = ui_support.test_results_h(package_name, latest_runtime, 
                                               test_id, hierarchy_id)
    else:
        test_results = ui_support.test_results(package_name, latest_runtime,
                                               test_id)
    if ((package == None) or (test_results==None)):
        abort(404)
    else:
        return jsonify(test_results)

@app.route('/api/publishers/<packagegroup_name>/hierarchy/<hierarchy_id>/tests/<test_id>/activities')
@app.route('/api/publishers/<packagegroup_name>/tests/<test_id>/activities')
@support_jsonp
def api_publisher_activities(packagegroup_name, test_id, hierarchy_id=None):
    if (("offset" in request.args) and (int(request.args['offset'])>=0)):
        offset = int(request.args['offset'])
    else:
        offset = 0
    packagegroup = ui_support.packagegroup_by_name(packagegroup_name)

    if (hierarchy_id):
        if (hierarchy_id=="None"): hierarchy_id=None
        test_count = get_test_count_h(packagegroup_name, test_id, 
                                      hierarchy_id)
        test_results = get_test_results_h(packagegroup_name, test_id, 
                                          hierarchy_id)
    else:
        # This is crude because it assumes there is only one result for this
        # test per activity-identifier. But that should be the case anyway.
        test_count = get_test_count(packagegroup_name, test_id)
        test_results = get_test_results(packagegroup_name, test_id)
    
    test_results = dict(map(lambda x: (x[0],x[1]), test_results))

    if ((packagegroup == None) or (test_results==None)):
        abort(404)
    else:
        return jsonify({"count": test_count, "results": test_results})

@app.route('/api/organisations/<organisation_code>/hierarchy/<hierarchy_id>/tests/<test_id>/activities')
@app.route('/api/organisations/<organisation_code>/tests/<test_id>/activities')
@support_jsonp
def api_organisation_activities(organisation_code, test_id, hierarchy_id=None):
    if (("offset" in request.args) and (int(request.args['offset'])>=0)):
        offset = int(request.args['offset'])
    else:
        offset = 0
    organisation = ui_support.organisation_by_code(organisation_code)

    if (hierarchy_id):
        if (hierarchy_id=="None"): 
            hierarchy_id = None
        test_results = get_org_test_results_h(organisation_code, test_id, 
                                              hierarchy_id)
    else:
        test_results = get_org_test_results(organisation_code, test_id)
    
    test_results = dict(map(lambda x: (x[0],x[1]), test_results))

    if ((organisation_code == None) or (test_results==None)):
        abort(404)
    else:
        return jsonify({"results": test_results})
