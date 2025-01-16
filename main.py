import os
from dotenv import load_dotenv
import pandas as pd
import requests
import datetime
import json
import numpy as np
from statsmodels.tsa.holtwinters import SimpleExpSmoothing


from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
from pymongo import MongoClient, UpdateOne

from dateutil.relativedelta import relativedelta
from peopledatalabs.get_monthly_salaries import get_company_payroll_batch


load_dotenv()
mongo_username = os.getenv("MONGO_ROOT_USERNAME")
mongo_password = os.getenv("MONGO_ROOT_PASSWORD")

# Connect to the MongoDB server
mongo_client = MongoClient("mongodb://${mongo_username}:${mongo_password}@localhost:27017/")
mongo_db = mongo_client["app"]
mongo_collection = mongo_db["final_data"]

HARMONIC_API_KEY = os.getenv("HARMONIC_API_KEY")
HARMONIC_SAVED_LIST_ID = "129643"


def batch_generator(lst: list[any], batch_size: int) -> any:
    """
    Yields batches of a given size from the list.
    """
    for i in range(0, len(lst), batch_size):
        yield lst[i : i + batch_size]


def convert_dates_to_datetimes(document):
    """Recursively convert all datetime.date objects to datetime.datetime in a document"""
    if isinstance(document, dict):
        for key, value in document.items():
            if isinstance(value, datetime.date) and not isinstance(
                value, datetime.datetime
            ):
                document[key] = datetime.datetime(value.year, value.month, value.day)
            elif isinstance(value, (dict, list)):
                convert_dates_to_datetimes(value)
    elif isinstance(document, list):
        for i in range(len(document)):
            if isinstance(document[i], datetime.date) and not isinstance(
                document[i], datetime.datetime
            ):
                document[i] = datetime.datetime(
                    document[i].year, document[i].month, document[i].day
                )
            elif isinstance(document[i], (dict, list)):
                convert_dates_to_datetimes(document[i])


def load_harmonic_into_db(list_id: str = HARMONIC_SAVED_LIST_ID, force: bool = False):
    """Loads data into the db from harmonic for later usage"""

    if not force:
        # check to see if we already have data
        if mongo_collection.find_one():
            return
    else:
        # clear the db
        mongo_collection.delete_many({})

    # Create the transport
    transport = RequestsHTTPTransport(
        url="https://api.harmonic.ai/graphql",
        headers={"apikey": HARMONIC_API_KEY},
        use_json=True,
    )
    gql_client = Client(transport=transport, fetch_schema_from_transport=False)
    query = gql(
        """
    query GetCompaniesWithMetadataInSavedSearchesByIdOrUrn($idOrUrn: String!, $cursor: String, $size: Int) {
        getCompaniesWithMetadataInSavedSearchesByIdOrUrn(idOrUrn: $idOrUrn, cursor: $cursor, size: $size) {
            pageInfo {
                current
                hasNext
                next
            }
            count
            companies {
                headcount
                name
                id
                website {
                    url
                    domain
                }
                tractionMetrics {
                    headcount {
                        metrics {
                            timestamp
                            metricValue
                        }
                    }
                }
                funding {
                    lastFundingAt
                    lastFundingTotal
                    fundingTotal
                    numFundingRounds
                }
            }
        }
    }
    """
    )

    # TODO: paginate query instead of just request for a much larger size than the current segment
    params = {"idOrUrn": list_id, "size": 1000}

    # Execute the query
    response = gql_client.execute(query, variable_values=params)
    companies = response["getCompaniesWithMetadataInSavedSearchesByIdOrUrn"][
        "companies"
    ]
    mongo_collection.insert_many(documents=companies)


def update_db_with_companies(companies: list[dict]):
    """
    Upserts the latest company info into the db
    """
    # Convert dates to datetimes
    for company in companies:
        convert_dates_to_datetimes(company)

    # Prepare bulk upsert operations
    operations = [
        UpdateOne(
            {"id": company["id"]},  # Filter by unique identifier
            {"$set": company},  # Update the document with new data
            upsert=True,  # Perform an upsert
        )
        for company in companies
    ]

    # Execute bulk upsert operations
    mongo_collection.bulk_write(operations)


def calculate_burndown_batched(companies: list[str]) -> list[list[int]]:
    """
    Calculation of cash spend per month based on monthly payroll. In a batched endpoint
    """
    get_company_payroll_batch(companies)


def calculate_etod(company: dict) -> dict:
    """
    Calculate the estimated time of death based on the burndown and funding total
    """
    print(f"calculating for {company['name']}")
    last_funding_date_raw = company["funding"]["lastFundingAt"]
    last_funding_datetime = datetime.datetime.strptime(
        last_funding_date_raw, "%Y-%m-%dT%H:%M:%SZ"
    )
    last_funding_date = last_funding_datetime.date()
    burn_rate = company.get("payroll")
    company["last_funding_date"] = last_funding_date
    if not burn_rate or len(burn_rate) == 0 or 0 in burn_rate.values():
        # We got no spend data for this company
        company["etod"] = None
        return
    # update the burn rate info into the company object
    company["burn_rate"] = burn_rate
    last_round_funding = company.get("funding").get("lastFundingTotal")

    remaining_funding = last_round_funding
    # Data
    values = np.array(list(burn_rate.values()))

    # Apply Exponential Smoothing
    model = SimpleExpSmoothing(values)
    model_fit = model.fit()

    if last_funding_date and last_round_funding:  # we have funding info
        months_alive = 0
        current_month = company["last_funding_date"]
        one_month = relativedelta(months=1)
        while remaining_funding > 0:
            # Pick a month off the burn rate list
            month_data = burn_rate.get(current_month.strftime("%Y-%m"))
            if month_data:
                # If we have data left in the list, then just subtract that data
                remaining_funding -= month_data
            else:
                # Extrapolate the current months data from the previous months data
                next_value = model_fit.forecast(months_alive + 1)[0]
                remaining_funding -= next_value
            months_alive += 1
            current_month += one_month

        timedelta_to_death = relativedelta(months=months_alive)
        time_of_death = last_funding_date + timedelta_to_death

        company["etod"] = time_of_death
    else:
        company["etod"] = None
    return company


def process_harmonic_list(list_urn: str = None):
    load_harmonic_into_db(list_urn)

    # First download data from Harmonic to get base truth
    harmonic_companies = list(mongo_collection.find())

    calculate_burndown_batched(harmonic_companies)

    # Then for each company calculate its estimated time of death
    for company in harmonic_companies:
        calculate_etod(company)

    update_db_with_companies(harmonic_companies)


if __name__ == "__main__":
    process_harmonic_list(HARMONIC_SAVED_LIST_ID)
