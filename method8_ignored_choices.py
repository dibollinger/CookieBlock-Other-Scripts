# Copyright (C) 2021 Dino Bollinger, ETH Zürich, Information Security Group
# Released under the MIT License
"""
Using a database of cookies specifically collected such that consent is rejected, find all cookies
from Cookiebot where we can verify that the consent was rejected.
----------------------------------
Required arguments:
    <db_path>   Path to database to analyze.
Usage:
    method8_ignored_choices.py <db_path>
"""
import os
import sqlite3

from docopt import docopt
import logging
from utils import (setupLogger, write_json, write_vdomains, retrieve_matched_cookies_from_DB)

CONSENTCOOKIE_REJECTED = '''SELECT DISTINCT site_url
FROM javascript_cookies j
JOIN site_visits s on s.visit_id == j.visit_id
JOIN consent_crawl_results cs on j.visit_id == cs.visit_id and cs.crawl_state == 0
WHERE j.name == "CookieConsent" and j.value like "%necessary:true%" and j.value like "%preferences:false%" 
      and j.value like "%statistics:false%" and j.value like "%marketing:false%"'''


def main():
    """
    Potential violation through implicit consent.
    @return: exit code, 0 for success
    """
    argv = None
    cargs = docopt(__doc__, argv=argv)

    logger = setupLogger(".", logging.INFO)

    logger.info("Running method 08: Ignored Choices")

    # Verify that database exists
    database_path = cargs["<db_path>"]
    if not os.path.exists(database_path):
        logger.error("Database file does not exist.")
        return 1

    logger.info(f"Database used: {database_path}")

    total_cookies = 0
    total_domains = set()

    # enable dictionary access by column name, access database
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row

    logger.info("Extracting info from database...")
    cookies_dict, _ = retrieve_matched_cookies_from_DB(conn)
    logger.info("--------------------------------------")
    logger.info("--------------------------------------")

    confirmed_rejected_domains = set()
    with conn:
        cur = conn.cursor()

        cur.execute(CONSENTCOOKIE_REJECTED)
        for row in cur:
            confirmed_rejected_domains.add(row["site_url"])
        logger.info(f"Total of {len(confirmed_rejected_domains)} domains for Cookiebot where consent was confirmed rejected.")

        cur.close()

    inconsistency_names = ["necessary", "functionality", "analytics", "advertising", "uncategorized", "social_media", "unknown"]
    inconsistency_counts = [0, 0, 0, 0, 0, 0, 0]
    inconsistency_domains = [set(), set(), set(), set(), set(), set(), set()]
    inconsistency_details = [{}, {}, {}, {}, {}, {}, {}]

    for key, val in cookies_dict.items():
        vdomain = val["site_url"]

        if vdomain in confirmed_rejected_domains:
            total_cookies += 1
            total_domains.add(val["site_url"])

            inconsistency_domains[val["label"]].add(vdomain)
            inconsistency_counts[val["label"]] += 1

            if vdomain not in inconsistency_details[val["label"]]:
                inconsistency_details[val["label"]][vdomain] = list()

            inconsistency_details[val["label"]][vdomain].append({**val})

    conn.close()

    logger.info(f"Number of cookies: {total_cookies}")
    logger.info(f"Total number of domains: {len(total_domains)}")
    logger.info(f"Cookie counts per class: {inconsistency_counts}")
    logger.info(f"Sum of functional, analytics and advertising: {sum(inconsistency_counts[1:4])}")

    os.makedirs("./violation_stats/method8/", exist_ok=True)
    for i in range(0, 5):
        logger.info("-------------------------------------------------------------")
        logger.info(f"Total number of domains that created a cookie of label '{inconsistency_names[i]}': {len(inconsistency_domains[i])}")

        v_per_cmp = [0, 0, 0]
        for url, violating_cookies in inconsistency_details[i].items():
            for c in violating_cookies:
                assert (c["cmp_type"] >= 0)
                v_per_cmp[c["cmp_type"]] += 1

        logger.info(f"Cookies per CMP Type: {v_per_cmp}")

        write_json(inconsistency_details[i], f"method8/method8_cookies_{inconsistency_names[i]}.json")
        write_vdomains(inconsistency_domains[i], f"method8/method8_domains_{inconsistency_names[i]}.txt")
    logger.info("-------------------------------------------------------------")

    return 0


if __name__ == "__main__":
    exit(main())
