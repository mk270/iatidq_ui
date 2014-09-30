
#  IATI Data Quality, tools for Data QA on IATI-formatted  publications
#  by Mark Brough, Martin Keegan, Ben Webb and Jennifer Smith
#
#  Copyright (C) 2013  Publish What You Fund
#
#  This programme is free software; you may redistribute and/or modify
#  it under the terms of the GNU Affero General Public License v3.0

from flask import Flask, render_template, flash, request, Markup, \
    session, redirect, url_for, escape, Response, abort, send_file
from flask.ext.login import login_required, current_user

from iatidataquality import app
import usermanagement

import iatidq.test_level as test_level

import os
import sys
import json

current = os.path.dirname(os.path.abspath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

from iatidq import  dqtests

test_list_location = "tests/activity_tests.csv"

@app.route("/tests/")
@app.route("/tests/<id>/")
def tests(id=None):
    def test_dict(t):
        tmp = dict(t.as_dict())
        tmp.update({
                "editor_url": url_for('tests_editor', id=t.id),
                "delete_url": url_for('tests_delete', id=t.id),
                "tests_url": url_for('tests', id=t.id)
                })
        return tmp

    if (id is not None):
        test = dqtests.tests(id)

        data = {
            "test": test_dict(test)
            }
        json_data = json.dumps(data, indent=2)

        return render_template("test.html", test=test, json_data=json_data,
             admin=usermanagement.check_perms('admin'),
             loggedinuser=current_user)

    tests = dqtests.tests()

    data = {
        "new_url": url_for('tests_new'),
        "import_url": url_for('import_tests'),
        "test": [ test_dict(t) for t in tests ]
        }

    json_data = json.dumps(data, indent=2)
    return render_template("tests.html", tests=tests,
                           admin=usermanagement.check_perms('admin'),
                           loggedinuser=current_user,
                           json_data=json_data)


## FIXME: coalesce parts with duplicated handler for template below
@app.route("/tests/<id>/edit/", methods=['GET', 'POST'])
@usermanagement.perms_required('tests', 'edit', '<id>')
def tests_editor(id=None):
    if (request.method == 'POST'):
        test = dqtests.tests(id)
        data = {
                "id": id,
                "name": request.form['name'],
                "description": request.form['description'],
                "test_level": request.form['test_level'],
                "active": request.form.get('active', None)
            }
        if dqtests.updateTest(data):
            flash('Updated', "success")
        else:
            flash("Couldn't update", "error")
    else:
        test = dqtests.tests(id)

    payload = test.as_dict()
    payload["active"] = test.active == 1

    json_data = json.dumps(payload, indent=2)

    return render_template("test_editor.html", test=test,
                           admin=usermanagement.check_perms('admin'),
                           json_data=json_data,
                           loggedinuser=current_user)

@app.route("/tests/<id>/delete/")
@usermanagement.perms_required('tests', 'delete', '<id>')
def tests_delete(id=None):
    if id is not None:
        if dqtests.deleteTest(id):
            flash('Successfully deleted test.', 'success')
        else:
            flash("Couldn't delete test. Maybe results already exist connected with that test?", 'error')
        return redirect(url_for('tests', id=id))
    else:
        flash('No test ID provided', 'error')
        return redirect(url_for('tests'))

@app.route("/tests/new/", methods=['GET', 'POST'])
@usermanagement.perms_required('tests', 'new')
@login_required
def tests_new():
    if (request.method == 'POST'):
        data = {
                "name": request.form['name'],
                "description": request.form['description'],
                "test_level": request.form['test_level'],
                "active": request.form.get('active', None)
            }
        try:
            test = dqtests.addTest(data)
            flash('Created', "success")
        except dqtests.TestNotFound:
            test = data
            flash('Unable to create. Maybe you already have a test using the same expression?', "error")

        payload = test.as_dict()
        payload["active"] = test.active == 1
    else:
        test = {}
        payload = {
            "id": "",
            "name": "",
            "description": "",
            "test_level": "",
            "active": True,
            "test_group": ""
            }

    json_data = json.dumps(payload, indent=2)

    return render_template("test_editor.html", test=test,
                           admin=usermanagement.check_perms('admin'),
                           json_data=json_data,
                           loggedinuser=current_user)


@app.route("/tests/import/", methods=['GET', 'POST'])
def import_tests():
    if (request.method == 'POST'):
        import dqimporttests
        if (request.form['password'] == app.config["SECRET_PASSWORD"]):
            if (request.form.get('local')):
                result = dqimporttests.importTestsFromFile(test_list_location, 
                                                           test_level.ACTIVITY)
            else:
                url = request.form['url']
                level = int(request.form['level'])
                result = dqimporttests.importTestsFromUrl(url, level=level)
            if (result==True):
                flash('Imported tests', "success")
            else:
                flash('There was an error importing your tests', "error")
        else:
            flash('Wrong password', "error")
    return render_template("import_tests.html",
             admin=usermanagement.check_perms('admin'),
             loggedinuser=current_user)
