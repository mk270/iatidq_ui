
#  IATI Data Quality, tools for Data QA on IATI-formatted  publications
#  by Mark Brough, Martin Keegan, Ben Webb and Jennifer Smith
#
#  Copyright (C) 2013  Publish What You Fund
#
#  This programme is free software; you may redistribute and/or modify
#  it under the terms of the GNU Affero General Public License v3.0

from flask import Flask, render_template, flash, request, Markup, \
    session, redirect, url_for, escape, Response, abort, send_file
from flask.ext.login import current_user

from iatidataquality import app
import usermanagement
import json

from iatidq import dqtests, dqaggregationtypes, dqusers

@app.route("/aggregationtypes/")
@app.route("/aggregationtypes/<aggregationtype_id>/")
@usermanagement.perms_required()
def aggregationtypes(aggregationtype_id=None):
    ats=dqaggregationtypes.aggregationTypes()

    def agg_type_and_test_as_dict(at):
        agt, test = at

        if test is None:
            test_description = ""
            test_url = ""
        else:
            test_description = test.description
            test_url = url_for('tests', id=test.id)

        return {
            "name": agt.name,
            "description": agt.description,
            "tests_url": test_url,
            "test_description": test_description,
            "test_result": agt.test_result,
            "edit_url": url_for('aggregationtypes_edit', 
                                aggregationtype_id=agt.id)
            }

    json_data = json.dumps({
            "edit_url": url_for('aggregationtypes_edit'),
            "aggregation_type" : [ agg_type_and_test_as_dict(at) for at in ats ]
            }, indent=2)
    
    return render_template("aggregation_types.html", aggregationtypes=ats,
             admin=usermanagement.check_perms('admin'),
             loggedinuser=current_user,
             json_data=json_data)

def get_aggregation_type(aggregationtype_id):
    def get_data():
        fields = ['name', 'description', 'test_id', 'test_result']
        return dict([ (f, request.form.get(f)) for f in fields ])

    if not request.method == 'POST':
        if aggregationtype_id:
            return dqaggregationtypes.aggregationTypes(
                aggregationtype_id)
        else:
            return {}
    else:
        data = get_data()
        if data['test_id']=="":
            data['test_id'] = None

        if aggregationtype_id:
            return \
                dqaggregationtypes.updateAggregationType(aggregationtype_id, 
                                                         data)
        else:
            return dqaggregationtypes.addAggregationType(data)

@app.route("/aggregationtypes/new/", methods=['POST', 'GET'])
@app.route("/aggregationtypes/<aggregationtype_id>/edit/", methods=['POST', 'GET'])
@usermanagement.perms_required()
def aggregationtypes_edit(aggregationtype_id=None):
    aggregationtype = get_aggregation_type(aggregationtype_id)

    if request.method == 'POST':
        if aggregationtype:
            flash('Successfully added your aggregation type.', 'success')
        else:
            aggregationtype = {}
            flash('Could not add your aggregation type.', 'error')

    tests = dqtests.tests()
    return render_template("aggregation_types_edit.html", 
                           aggregationtype=aggregationtype, tests=tests,
                         admin=usermanagement.check_perms('admin'),
                         loggedinuser=current_user)
