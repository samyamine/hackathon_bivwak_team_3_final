
# Startup Runway Estimator

![alt text](https://i.imgur.com/O8vZHPM.png)

> This project was built as part of the Data-Driven VC Hackathon organized by [Red River West](https://redriverwest.com) & [Bivwak! by BNP Paribas](https://bivwak.bnpparibas/)

## Description
The **Startup Runway Estimator** helps venture capitalists (VCs) project a startup’s financial runway by analyzing revenue and costs month by month. This tool leverages data from external sources, including People Data Labs, SimilarWeb, and Harmonic, combined with salary benchmarks, to provide actionable insights into a startup’s financial health and projected time until cash depletion.

---

## Prerequisites

### Environment
- Python 3.9+
- Docker (for MongoDB and Mongo Express)

### API Keys
To run the project, you’ll need API keys for the following services:
- **People Data Labs (PDL)**: To fetch headcount data.
- **Harmonic**: To filter and select target companies.
- **GPT API**: To estimate revenue using website traffic and employee data.

### Libraries
Install the required Python libraries by running:
```bash
pip install -r requirements.txt
```

---

## Setup

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_REPO_URL
cd YOUR_PROJECT_NAME
```

### 2. Set Up the Environment
Create a `.env` file in the project root and include the following variables:
```env
HARMONIC_API_KEY=your_harmonic_api_key
PDL_API_KEY=your_pdl_api_key
GPT_API_KEY=your_gpt_api_key
```

### 3. Start the Database
Use Docker to start the MongoDB and Mongo Express services:
```bash
docker-compose up
```
This will:
- Start MongoDB on `localhost:27017`
- FastAPI on `localhost:8000`

### 4. Populate the Database
Load initial data from Harmonic by clicking the "synchronise database" button on the application:
```bash
python main.py
```
This fetches company data from Harmonic and populates the MongoDB database.

---

## Usage

### Running the API
Start the FastAPI server:
```bash
uvicorn backend:app --reload
```
- **API Endpoints:**
  - `GET /`: Returns a welcome message.
  - `POST /data`: Placeholder for future data endpoints.

### Calculating Runway
The `main.py` script calculates and updates each company’s **Estimated Time of Death (ETOD)** in the MongoDB database. It uses:
- **Revenue estimates** from the GPT API (using website traffic and employee data).
- **Cost projections** based on salary benchmarks and headcount data.
- Funding data from Harmonic.

---

## Customization

### Modifying Salary Benchmarks
The salary benchmarks used in the calculation can be updated in `get_monthly_salaries.py`:
```python
salaries = {
    "engineering": 4160,
    "sales": 4000,
    "marketing": 3660,
    # Add or modify as needed
}
```

### Adjusting Multipliers
Adjust salary ratios for roles and seniority in the same file:
```python
salary_ratios = {
    "entry": 0.7,
    "senior": 1.3,
    "manager": 1.5,
    # Add or modify as needed
}
```

### GPT Prompt Adjustments
Update the prompts used for revenue calculation in the `retrieve_sw` function within `main.py`.

---

## Limitations
- **Revenue Estimation**: The model relies on GPT and website traffic data, which may not accurately reflect B2B SaaS revenue.
- **Assumptions**: Salary data and multipliers are based on benchmarks for France and may not generalize globally.
- **Data Sources**: SimilarWeb data relevance varies, especially for B2C startups.

---

## License
This project is licensed under the MIT License. See the `LICENSE` file for details.

---

## Contributing
Contributions are welcome! Please open an issue or submit a pull request for bugs, improvements, or new features.