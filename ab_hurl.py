#!/usr/bin/env python3

'''
ab_hurl.py A Wrapper around hurl to be used to load test our instances.
Still working on the specifics

CSV From Nexus:
```
SELECT
    id,env_name,name,version,status,last_updated,sf_account_id,ab_site_id
FROM
    analytics_site
WHERE
   status = 'up' AND env_name = 'QA'
ORDER BY
    analytics_site.Name ASC
```

'''

import argparse
import logging
import subprocess
import csv
import string
import urllib.parse
import time
import json

import requests

ADMIN_USER = "ops@soxhub.com"

LOGIN = "/api/v1/users/login"

if __name__ == "__main__":

    """
    Let's grab my runtime options
    """

    parser = argparse.ArgumentParser()

    parser.add_argument("-v", "--verbose", action="append_const", help="Verbosity Controls",
                        const=1, default=[])
    parser.add_argument("-s", "--sitescsv", help="Nexus CSV File", required=True)
    parser.add_argument("-p", "--password", help="Admin Password", required=True)
    parser.add_argument("-l", "--limit", help="Site Limit", default=10, type=int)
    parser.add_argument("-t", "--timeout", help="Seconds to timeout", type=int, default=100)


    args = parser.parse_args()

    VERBOSE = len(args.verbose)

    if VERBOSE == 0:
        logging.basicConfig(level=logging.ERROR)
    elif VERBOSE == 1:
        logging.basicConfig(level=logging.WARNING)
    elif VERBOSE == 2:
        logging.basicConfig(level=logging.INFO)
    elif VERBOSE > 2:
        logging.basicConfig(level=logging.DEBUG)

    logger = logging.getLogger("ab_hurl")

def main(args, limit=10):

    logger = logging.getLogger("ab_hurl::main")

    cmd_tmpl = string.Template("docker run hurl:latest ${url} -l ${timeout} -H 'token: ${token}'")

    cmds = dict()

    sites = 0

    with open(args.sitescsv) as csvfobj:
        sites_data = csv.DictReader(csvfobj)

        for row in sites_data:

            cmds[row["name"]] = dict()

            token = get_token(row["name"], admin_pass=args.password)

            logger.debug(token)

            if token is None:
                logger.warning("Not Using Site: {} as I can't login".format(row["name"]))
                cmds[row["name"]]["complete"] = True
                cmds[row["name"]]["notoken"] = True
                continue
            else:

                sites += 1

                url = urllib.parse.urljoin("https://{}/".format(row["name"]), "api/v1/settings")

                logger.warning("Running against : {}".format(url))

                cmd = cmd_tmpl.safe_substitute(url=url,
                                               timeout=args.timeout,
                                               token=token)

                logger.info("Running Command: {}".format(cmd))

                cmds[row["name"]]["process"] = subprocess.Popen(cmd, shell="/bin/bash", stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            if sites >= limit:
                logger.info("Maximum Sites Hit : {}".format(limit))
                break



    running_procs = True
    while running_procs:
        running_procs = 0
        for site, data in cmds.items():
            if data.get("complete", False) is True:
                # Site has been completed
                pass
            else:
                returncode = data["process"].poll()

                if returncode is not None:
                    # Process has been completed
                    logger.debug("Process for {} has completed.".format(site))
                    cmds[site]["complete"] = True

                    stdout, sterr = data["process"].communicate()

                    print(stdout.decode())
                else:
                    # Process Still Running
                    logger.debug("Process for {} still running.".format(site))
                    running_procs += 1

        time.sleep(5)

    #print(json.dumps(cmds), default=str)

def get_token(site=None, admin_user=ADMIN_USER, admin_pass=None):

    """
    :param site:
    :param admin_user:
    :return:
    """
    token = None

    logger = logging.getLogger("ab_hurl::get_token")

    post_body = {"credentials": {"email": admin_user, "password": admin_pass}}

    url = urllib.parse.urljoin("https://{}/".format(site), LOGIN)

    try:
        response = requests.post(url, json=post_body, timeout=10)
    except Exception as error:
        logger.error("Unable to Get Token for {}, ignoring.".format(site))
    else:

        if response.ok:
            token = response.json()["session"]["token"]
        else:
            logger.error("Unable to Get Token for {} with response: {}".format(site, response.status_code))

    return token


if __name__ == "__main__":

    main(args, limit=args.limit)
