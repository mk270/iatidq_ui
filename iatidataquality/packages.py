
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

from iatidq import dqdownload, dqregistry, dqindicators, dqorganisations, dqpackages, summary, dqaggregationtypes, dqusers, ui_support

import json

import usermanagement

def integerise(data):
    try:
        return int(data)
    except ValueError:
        return None
    except TypeError:
        return None

def pkg_as_dict(p):
    pkg = dict(p.as_dict())
    pkg["packages_url"] = url_for('packages', id=p.package_name)
    pkg["man_auto"] = p.man_auto == "man"
    pkg["edit_url"] = url_for('packages_edit', 
                              package_name=p.package_name)
    return pkg

@app.route("/packages/manage/", methods=['GET', 'POST'])
@usermanagement.perms_required()
def packages_manage():
    if request.method != 'POST':
        pkgs = ui_support.package_in_order()
        data = {
            "pkg": [ pkg_as_dict(pkg) for pkg in pkgs ]
            }
        json_data = json.dumps(data, indent=2)

        return render_template("packages_manage.html", 
             pkgs=pkgs,
             json_data=json_data,
             admin=usermanagement.check_perms('admin'),
             loggedinuser=current_user)

    if "refresh" in request.form:
        dqregistry.refresh_packages()
        flash("Refreshed packages from Registry", "success")
    else:
        data = []
        for package in request.form.getlist('package'):
            try:
                request.form["active_"+package]
                active=True
            except Exception:
                active=False
            data.append((package, active))
        dqregistry.activate_packages(data)
        flash("Updated packages", "success")
    return redirect(url_for('packages_manage'))

                   
@app.route("/packages/new/", methods=['POST', 'GET'])
@app.route("/packages/<package_name>/edit/", methods=['POST', 'GET'])
def packages_edit(package_name=None):
    if request.method=='GET':
        if package_name is not None:
            package = dqpackages.packages_by_name(package_name)
            # Get only first organisation (this is a hack,
            # but unlikely we will need to add a package
            # to more than one org)
            try:
                package_org_id = dqpackages.packageOrganisations(package.id)[0].Organisation.id
            except IndexError:
                package_org_id=None
            if package.man_auto=='auto':
                flash("That package is not a manual package, so it can't be edited.", 'error')
                return redirect(url_for('packages'))
        else:
            package ={}
            package_org_id = ""
        organisations=dqorganisations.organisations()
        return render_template("package_edit.html", 
             package=package,
             package_org_id = package_org_id,
             organisations=organisations,
             admin=usermanagement.check_perms('admin'),
             loggedinuser=current_user)
    else:
        if 'active' in request.form:
            active = True
        else:
            active = False

        data = {
            'package_name' : request.form.get('package_name'),
            'package_title' : request.form.get('package_title'),
            'source_url' : request.form.get('source_url'),
            'man_auto' : 'man',
            'active': active,
            'hash': request.form.get('hash')
        }
        package_org_id=request.form.get('organisation')
        if package_name is not None:
            pkg = dqpackages.packages_by_name(package_name)
            data['package_id'] = pkg.id
            package = dqpackages.updatePackage(data)
            mode = 'updated'
        else:
            data['package_name'] = 'manual_' + data['package_name']
            package = dqpackages.addPackage(data)
            mode = 'added'
        if package:
            if (package_org_id is not None) and (package_org_id != ""):
                pkorg = dqorganisations.addOrganisationPackage({
                    'organisation_id': package_org_id,
                    'package_id': package.id,
                    'condition': None
                })
            # TODO: attach package to organisation
            flash("Successfully "+mode+" package.", 'success')
            return redirect(url_for('packages_edit', package_name=package.package_name))
        else:
            flash("There was an error, and the package could not be "+mode+".", "error")
            organisations=dqorganisations.organisations()
            data['package_name'] = request.form.get('package_name')
        return render_template("package_edit.html", 
             package=data,
             package_org_id = package_org_id,
             organisations=organisations,
             admin=usermanagement.check_perms('admin'),
             loggedinuser=current_user)

@app.route("/packages/")
@app.route("/packages/<package_name>/")
def packages(package_name=None):
    if package_name is None:
        packages = ui_support.active_packages_in_order()

        payload = {
            "manage_url": url_for('packages_manage'),
            "pkg": [ pkg_as_dict(p) for p in packages ]
            }
        json_data = json.dumps(payload, indent=2)

        return render_template("packages.html", 
             packages=packages, json_data=json_data,
             admin=usermanagement.check_perms('admin'),
             loggedinuser=current_user)

    # Get package data
    package = ui_support.get_package_data(package_name)

    # see older code in repo for what used to be here
    pconditions = {}

    latest_runtime = None

    aggregation_type=integerise(request.args.get('aggregation_type', 2))
    all_aggregation_types = dqaggregationtypes.aggregationTypes()

    # this test should really ask "have we ever had an aggregation"
    
    if latest_runtime:
        summary_results = summary.PackageSummaryCreator(
            package[0].id, latest_runtime, aggregation_type).summary
    else:
        summary_results = None
        pconditions = None
        flat_results = None

    organisations = dqpackages.packageOrganisations(package.Package.id)
 
    return render_template("package.html", package=package, 
                           results=summary_results, 
                           pconditions=pconditions,
                           organisations=organisations,
                           all_aggregation_types=all_aggregation_types,
                           aggregation_type=aggregation_type,
                           admin=usermanagement.check_perms('admin'),
                           loggedinuser=current_user)
