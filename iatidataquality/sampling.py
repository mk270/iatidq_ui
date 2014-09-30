
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

from iatidq import dqusers, util, dqorganisations, dqtests, dqindicators, \
    dqcodelists

import unicodecsv
import json

import lxml.etree

import os
from sqlite3 import dbapi2 as sqlite
import sqlite3
from sample_work import sample_work
from sample_work import db as sample_db
from sample_work import test_mapping

def memodict(f):
    """ Memoization decorator for a function taking a single argument """
    class memodict(dict):
        def __missing__(self, key):
            ret = self[key] = f(key)
            return ret 
    return memodict().__getitem__

@memodict
def get_test_info(test_id):
    return dqtests.tests(test_id)

@memodict
def get_test_indicator_info(test_id):
    return dqindicators.testIndicator(test_id)

@memodict
def get_org_info(organisation_id):
    return dqorganisations.organisation_by_id(organisation_id)

def get_response(kind, response, unsure):
    def get_unsureness(unsure):
        if (unsure == 1):
            return '<a class="btn btn-danger btn-mini"><i class="icon icon-white icon-info-sign"></i> <b>Unsure</b></a>'
        return ""


    kind_data = test_mapping.kind_to_status[kind]
    response_data = kind_data.get(response)
    
    if response_data is not None:
        response_data['unsure'] = get_unsureness(unsure)
        return response_data
    return {
              "text:": "not yet sampled",
              "button": "not yet sampled",
              "icon": "info-sign",
              "class": "warning",
            }

def kind_to_list(kind):
    kind_data = test_mapping.kind_to_status[kind]
    kind_data = map(lambda x: (x[1]), kind_data.items())
    return kind_data

def make_sample_json(work_item):
    def get_docs(xml_strings):

        def get_doc_from_xml(xml):
            if xml == None:
                return []
            document_category_codes = dqcodelists.reformatCodelist('DocumentCategory')
            document_links = sample_work.DocumentLinks(work_item["xml_data"], 
                                               document_category_codes)
            docs = [ dl.to_dict() for dl in document_links.get_links() ]
            return docs

        data = [get_doc_from_xml(xml) for xml in xml_strings]
        return data[0]+data[1]

    def get_res(xml_strings):
        def get_res_from_xml(xml):
            if xml == None:
                return []
            results = sample_work.Results(work_item["xml_data"])
            res = [ ln.to_dict() for ln in results.get_results() ]
            return res
        
        data = [get_res_from_xml(xml) for xml in xml_strings]
        return data[0]+data[1]

    def get_locs(xml_strings):
        def get_loc_from_xml(xml):
            if xml == None:
                return []
            locations = sample_work.Locations(work_item["xml_data"])
            locs = [ ln.to_dict() for ln in locations.get_locations() ]
            return locs
    
        data = [get_loc_from_xml(xml) for xml in xml_strings]
        return data[0]+data[1]

    def get_conds(xml_strings):
        def get_cond_from_xml(xml):
            if xml == None:
                return []
            conditions = [sample_work.Conditions(work_item["xml_data"]).get_conditions()]
            return conditions
        data = [get_cond_from_xml(xml) for xml in xml_strings]
        return data[0]+data[1]        

    xml_strings = [work_item["xml_data"],
                   work_item["xml_parent_data"]]
    docs = get_docs(xml_strings)
    
    
    if work_item["test_kind"] == "location":
        locs = get_locs(xml_strings)
    else:
        locs = []

    if work_item["test_kind"] == "result":
        res = get_res(xml_strings)
    else:
        res = []

    if work_item["test_kind"] == "conditions":
        conditions = get_conds(xml_strings)
    else:
        conditions = []

    activity_info = sample_work.ActivityInfo(work_item["xml_data"])

    work_item_test = get_test_info(work_item["test_id"])
    work_item_indicator = get_test_indicator_info(work_item["test_id"])
    work_item_org = get_org_info(work_item["organisation_id"])

    xml = work_item['xml_data']

    data = { "sample": {
                "iati-identifier": work_item["activity_id"],
                "documents": docs,
                "locations": locs,
                "results": res,
                "conditions": conditions,
                "sampling_id": work_item["uuid"],
                "test_id": work_item["test_id"],
                "organisation_id": work_item["organisation_id"],
                "activity_title": activity_info.title,
                "activity_description": activity_info.description,
                "test_kind": work_item["test_kind"],
                "xml": xml,
            },
            "headers": {
                "test_name": work_item_test.name,
                "test_description": work_item_test.description,
                "indicator_name": work_item_indicator.description,
                "indicator_description": work_item_indicator.longdescription,
                "organisation_name": work_item_org.organisation_name,
                "organisation_code": work_item_org.organisation_code,
            },
            "buttons": kind_to_list(work_item["test_kind"]),
            "response": {}
        }
    if 'response' in work_item:
        data['response'] = get_response(work_item["test_kind"], 
                    work_item['response'], 
                    work_item['unsure'])

    return data


@app.route("/api/sampling/process/", methods=['POST'])
@app.route("/api/sampling/process/<response>", methods=['POST'])
@usermanagement.perms_required()
def api_sampling_process(response):
    data = request.form
    try:
        unsure = 'unsure' in data
        assert 'sampling_id' in data
        work_item_uuid = data["sampling_id"]
        response = int(response)

        sample_db.save_response(work_item_uuid, response, unsure)
        return 'OK'
    except sqlite3.IntegrityError:
        return "EXISTS"
    except Exception as e:
        return 'ERROR'


@app.route("/api/sampling/update/", methods=['POST'])
@app.route("/api/sampling/update/<response>", methods=['POST'])
@usermanagement.perms_required()
def api_sampling_update(response):
    data = request.form
    try:
        unsure = 'unsure' in data
        assert 'sampling_id' in data
        work_item_uuid = data["sampling_id"]
        response = int(response)

        sample_db.update_response(work_item_uuid, response, unsure)
        flash('Updated response for that sample', 'success')
        return url_for('sampling_list')
    except AssertionError:
        return "NO SUCH UUID"
    except Exception as e:
        return 'ERROR'

@app.route("/api/sampling/")
@app.route("/api/sampling/<uuid>/")
@usermanagement.perms_required()
def api_sampling(uuid=None):
    if not uuid:
        try:
            results = sample_db.work_item_generator(make_sample_json)
        except sample_db.NoMoreSamplingWork:
            results = {
                "error": "Finished"
                }
        #except:
        #    results = {
        #        "error": "Unknown"
        #        }
    else:
        def make_wi(uuid):
            return sample_db.read_db_response(uuid).next()
        results = make_sample_json(make_wi(uuid))
    return json.dumps(results, indent=2)


@app.route("/sampling/")
@app.route("/sampling/<uuid>/")
@usermanagement.perms_required()
def sampling(uuid=None):
    if uuid:
        update = "true"
        api_process_url = url_for('api_sampling_update')
        api_sampling_url = url_for('api_sampling', uuid=uuid)
    else:
        update = "false"
        api_process_url = url_for('api_sampling_process')
        api_sampling_url = url_for('api_sampling')
    return render_template("sampling.html",
         admin=usermanagement.check_perms('admin'),
         loggedinuser=current_user,
         update=update,
         api_process_url=api_process_url,
         api_sampling_url=api_sampling_url)

@app.route("/sampling/list/")
@usermanagement.perms_required()
def sampling_list():
    samples = []
    for wi in sample_db.read_db_response():
        samples.append(make_sample_json(wi))
    return render_template("sampling_list.html",
         admin=usermanagement.check_perms('admin'),
         loggedinuser=current_user,
         samples=samples)

@app.route("/sampling/orglist/")
@usermanagement.perms_required()
def sampling_orglist():
    orgtests = sample_db.get_total_results()
    data = sample_db.get_summary_org_test(orgtests)
    return render_template("sampling_org_tests.html",
         admin=usermanagement.check_perms('admin'),
         loggedinuser=current_user,
         orgtests=data)
