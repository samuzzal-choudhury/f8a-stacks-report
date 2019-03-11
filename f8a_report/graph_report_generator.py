"""Helper functions related to to generate ingestion reports."""

from f8a_utils.versions import get_latest_versions_for_ep
import logging
import os
import requests
import traceback
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

_logger = logging.getLogger(__name__)
GREMLIN_SERVER_URL_REST = "http://gremlin-yzainee-fabric8-analytics.devtools-dev.ext.devshift.net"
"""
GREMLIN_SERVER_URL_REST = "http://{host}:{port}".format(
    host=os.environ.get("BAYESIAN_GREMLIN_HTTP_SERVICE_HOST", "localhost"),
    port=os.environ.get("BAYESIAN_GREMLIN_HTTP_SERVICE_PORT", "8182")) """

GREMLIN_QUERY_SIZE = os.getenv('GREMLIN_QUERY_SIZE', 50)

"""
TODO: WIP
def generate_report_for_cves(cve_list):
    Generate a report for CVEs.

    :param cve_list: list, list of CVEs
    :return json, list of cve information

    query_str = "g.V().has('pecosystem', '{arg0}')." \
                "has('pname', '{arg1}').has('version', '{arg2}')" \
                ".valueMap().dedup().fill(epv);"
    report_result = {}
    args = []
"""


def generate_report_for_unknown_epvs(epv_list):
    """Generate a report for the unknown EPVs.

    :param epv_list: list, list of EPVs
    :return json, list of epv information
    """
    query_str = "g.V().has('pecosystem', '{arg0}')." \
                "has('pname', '{arg1}').has('version', '{arg2}')" \
                ".valueMap().dedup().fill(epv);"
    report_result = {}
    args = []
    for epv in epv_list:
        eco = epv['ecosystem']
        pkg = epv['name']
        ver = epv['version']
        args.append({
            "0": eco,
            "1": pkg,
            "2": ver
        })
        report_result[eco + ":" + pkg + ":" + ver] = "false"

    result_data = batch_query_executor(query_str, args)
    if result_data is not None:
        for res in result_data:
            eco = res['pecosystem'][0]
            pkg = res['pname'][0]
            ver = res['version'][0]
            report_result[eco + ":" + pkg + ":" + ver] = "true"
    return report_result


def generate_report_for_latest_version(epv_list):
    """Generate a report for the latest version.

    :param epv_list: list, list of EPVs
    :return json, list of version information
    """
    query_str = "g.V().has('ecosystem', '{arg0}')." \
                "has('name', '{arg1}')" \
                ".valueMap().dedup().fill(epv);"
    report_result = {}
    args = []
    for epv in epv_list:
        args.append({
            "0": epv['ecosystem'],
            "1": epv['name']
        })

    result_data = batch_query_executor(query_str, args)
    if result_data is not None:
        for res in result_data:
            eco = res['ecosystem'][0]
            pkg = res['name'][0]
            latest_pkg_version = res['latest_version'][0]
            latest = get_latest_versions_for_ep(eco, pkg)
            tmp = {
                "ecosystem": eco,
                "name": pkg,
                "known_latest_version": latest_pkg_version,
                "actual_latest_version": latest
            }
            report_result[eco + ":" + pkg] = tmp

    return report_result


def execute_gremlin_dsl(payload, url=GREMLIN_SERVER_URL_REST):
    """Execute the gremlin query and return the response."""
    try:
        response = get_session_retry().post(url, json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            _logger.error(
                "HTTP error {code}. Error retrieving data from {url}.".format(
                    code=response.status_code, url=url))
            return None

    except Exception:
        _logger.error(traceback.format_exc())
        return None


def get_session_retry(retries=3, backoff_factor=0.2, status_forcelist=(404, 500, 502, 504),
                      session=None):
    """Set HTTP Adapter with retries to session."""
    session = session or requests.Session()
    retry = Retry(total=retries, read=retries, connect=retries,
                  backoff_factor=backoff_factor, status_forcelist=status_forcelist)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    return session


def get_response_data(json_response, data_default):
    """Retrieve data from the JSON response.

    Data default parameters takes what should data to be returned.
    """
    return json_response.get("result", {}).get("data", data_default)


def batch_query_executor(query_string, args):
    """Execute the gremlin query in batches of 50."""
    query = "epv=[];"
    tmp_query = ""
    counter = 0
    result_data = []
    for arg in args:
        if len(arg) == 2:
            tmp_query = query_string.format(arg0=arg['0'], arg1=arg['1'])
            counter += 1
        elif len(arg) == 3:
            tmp_query = query_string.format(arg0=arg['0'], arg1=arg['1'], arg2=arg['2'])
            counter += 1
        if counter == 1:
            query = "epv=[];"
        query += tmp_query

        if counter >= GREMLIN_QUERY_SIZE:
            counter = 0
            payload = {'gremlin': query}
            gremlin_response = execute_gremlin_dsl(payload)
            if gremlin_response is not None:
                result_data += get_response_data(gremlin_response, [{0: 0}])
            else:
                _logger.error("Error while trying to fetch data from graph. "
                              "Expected response, got None...Query->", query)

    if counter < GREMLIN_QUERY_SIZE:
        payload = {'gremlin': query}
        gremlin_response = execute_gremlin_dsl(payload)
        if gremlin_response is not None:
            result_data += get_response_data(gremlin_response, [{0: 0}])
        else:
            _logger.error("Error while trying to fetch data from graph. "
                          "Expected response, got None...Query->", query)

    return result_data


"""
if __name__ == "__main__":
    print("start")
    list = [{
            "ecosystem": "maven",
            "name": "io.vertx:vertx-web"
            },
            {
                "ecosystem": "npm",
                "name": "lodash"
            },
            {
                "ecosystem": "maven",
                "name": "io.vertx:lang-groovy"
            },
            {
                "ecosystem": "pypi",
                "name": "requests"
            }]
    generate_report_for_latest_version(list)

    list = [{
                "ecosystem": "maven",
                "name": "io.vertx:vertx-web",
                "version": "3.6.3"
            },
            {
                "ecosystem": "npm",
                "name": "lodash",
                "version": "2.40.1"
            },
            {
                "ecosystem": "maven",
                "name": "io.vertx:lang-groovy",
                "version": "2.1.1-final"
            },
            {
                "ecosystem": "pypi",
                "name": "requests",
                "version": "2.21.0"
            }]
    generate_report_for_unknown_epvs(list)
    print("end")
"""
