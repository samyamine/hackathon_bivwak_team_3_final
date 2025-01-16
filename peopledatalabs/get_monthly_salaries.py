import os
import requests
import json
import time
import numpy as np
from datetime import datetime
from ratelimit import limits, sleep_and_retry


def format_date(date):
    date_object = datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")

    # Format the datetime object to "YYYY-MM"
    return date_object.strftime("%Y-%m")


@sleep_and_retry
@limits(calls=10, period=60)
def get_companies(websites):
    PDL_API_KEY = os.getenv("PDL_API_KEY")
    url = "https://api.peopledatalabs.com/v5/company/search"

    array_string = ", ".join(f"'{website}'" for website in websites)
    params = {
        "sql": f"SELECT * FROM company WHERE website IN ({array_string})",
        "size": 5,
    }

    headers = {
        "accept": "application/json",
        "X-API-Key": PDL_API_KEY,
    }

    response = requests.get(url, headers=headers, params=params)

    return json.loads(response.text)


def truncate_time_series(dictionary, start_date):
    start_date = datetime.strptime(start_date, "%Y-%m")

    res = {
        key: value
        for key, value in dictionary.items()
        if datetime.strptime(key, "%Y-%m") >= start_date
    }

    return res


def get_company_payroll(company, start_date=None):
    """
    Computes payroll per month for a given company.

    Args:
        company (dict): Company to compute payroll for
        start_date (string, optional): Date to compute payroll from. Defaults to None.

    Returns:
        dict: the monthly payroll for the given company
    """
    salaries = {
        "other_uncategorized": 4016,
        "trades": 6854,
        "operations": 3196,
        "customer_service": 2411,
        "legal": 3963,
        "public_relations": 3196,
        "real_estate": 2882,
        "design": 2411,
        "education": 3510,
        "media": 3196,
        "marketing": 3196,
        "human_resources": 3510,
        "sales": 3196,
        "health": 4526,
        "finance": 5662,
        "engineering": 5090,
    }

    salary_ratios = {
        "entry": 1,
        "unpaid": 0,
        "senior": 1.64,
        "director": 3.83,
        "vp": 5.56,
        "training": 0.5,
        "manager": 2.12,
        "owner": 2.5,
        "partner": 2.5,
        "cxo": 2.5,
    }

    result = dict()
    monthly_payroll = []

    # 2. We compute salary budget
    employee_count_by_month_by_role = (
        truncate_time_series(company["employee_count_by_month_by_role"], start_date)
        if start_date
        else company["employee_count_by_month_by_role"]
    )

    employee_count_by_month_by_level = (
        truncate_time_series(company["employee_count_by_month_by_level"], start_date)
        if start_date
        else company["employee_count_by_month_by_level"]
    )

    times = list(employee_count_by_month_by_level.keys())

    # Casting dicts into arrays
    salaries = list(salaries.values())
    salary_ratios = list(salary_ratios.values())

    # Month loop
    for roles, experiences in zip(
        employee_count_by_month_by_role.values(),
        employee_count_by_month_by_level.values(),
    ):
        current_month = 0

        # Computing experience ratios
        experience_sum = np.sum(list(experiences.values()))
        experience_ratios = []

        for experience in experiences.values():
            if experience != 0:
                experience_ratios.append(experience / experience_sum)

        # Computing the monthly salary budget
        roles_counts = list(roles.values())

        for i in range(len(roles_counts)):
            for j in range(len(experience_ratios)):
                current_month += (
                    roles_counts[i]
                    * salaries[i]
                    * experience_ratios[j]
                    * salary_ratios[j]
                )

        monthly_payroll.append(current_month)

    for time, payroll in zip(times, monthly_payroll):
        result[time] = round(payroll, 2)

    return result


def get_company_payroll_batch(
    companies, start_dates=None, max_retries=5, retry_delay=1
):
    """
    Returns the total monthly payroll for a batch of companies.

    Args:
        companies (str): the website urls of the companies.
        start_dates: the start date to consider for each company.
        max_retries (int): maximum number of retries on 429 errors.
        retry_delay (int): initial delay (in seconds) before retrying.

    Returns:
        salary_budgets: a list of all monthly payrolls for the given companies.
    """
    if not start_dates:
        start_dates = [None] * len(companies)

    # 1. We retrieve data
    domains = [company["website"]["domain"] for company in companies]
    domains = [domains[i : i + 5] for i in range(0, len(domains), 5)]
    companies = [companies[i : i + 5] for i in range(0, len(companies), 5)]

    for domain_batch, companies_batch in zip(domains, companies):
        print(f"Fetching data for {domain_batch}...")
        retries = 0
        while retries < max_retries:
            data = get_companies(domain_batch)
            status = data["status"]

            if status == 200:
                break  # Proceed if the status is OK
            elif status == 429:
                retries += 1
                wait_time = retry_delay * (2**retries)
                print(f"Rate limit hit. Retrying in {wait_time:.2f} seconds...")
                time.sleep(wait_time)  # Wait before retrying
            else:
                print(len(companies_batch))
                raise Exception(
                    f"Error: {data}"
                )  # Raise for other errors like 5xx or network issues

        if retries == max_retries:
            raise Exception(
                f"Max retries reached. Unable to fetch data for {domain_batch}"
            )

        # Process the data if no errors
        data = data["data"]

        # 2. We compute salary budget
        for i in range(len(data)):
            company_data = data[i]
            payrolls = get_company_payroll(company_data, start_date=start_dates[i])

            if len(data) < len(companies_batch):
                for j in range(len(companies_batch)):
                    if (
                        companies_batch[j]["website"]["domain"]
                        == company_data["website"]
                    ):
                        companies_batch[j]["payroll"] = payrolls
            else:
                companies_batch[i]["payroll"] = payrolls

    return companies  # Returning the updated list with payrolls
