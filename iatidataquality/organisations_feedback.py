
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

from iatidq import dqdownload, dqregistry, dqindicators, dqorganisations, dqpackages, dqusers

import usermanagement
import json

@app.route("/organisations/<organisation_code>/feedback/", methods=['POST', 'GET'])
@usermanagement.perms_required('organisation_feedback', 'create')
def organisations_feedback(organisation_code=None):
    if organisation_code is None:
        flash('No organisation supplied', 'error')
        return redirect(url_for('organisations'))

    organisation = dqorganisations.organisations(organisation_code)
    if (request.method=="POST"):
        for condition in request.form.getlist('feedback'):
            data = {
                'organisation_id': organisation.id,
                'uses': request.form['uses'+condition],
                'element': request.form['element'+condition],
                'where': request.form['where'+condition]
                }
            if dqorganisations.addFeedback(data):
                flash('Successfully added condition.', 'success')
            else:
                flash("Couldn't add condition.", 'error')

    payload = organisation.as_dict()
    payload.update({
        "org_url": url_for('organisations', 
			   organisation_code=organisation.organisation_code)
        })

    json_data = json.dumps(payload, indent=2)

    return render_template("organisation_feedback.html", 
                           organisation=organisation,
                           json_data=json_data,
                           admin=usermanagement.check_perms('admin'),
                           loggedinuser=current_user)
       

