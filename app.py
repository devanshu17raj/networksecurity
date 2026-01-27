import sys
import os
import certifi
import boto3  # <--- Added to connect to Cloudflare
import pymongo
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- 1. MongoDB Setup ---
ca = certifi.where()
mongo_db_url = os.getenv("MONGO_DB_URL")
client = pymongo.MongoClient(mongo_db_url, tlsCAFile=ca)

from networksecurity.exception.exception import NetworkSecurityException
from networksecurity.logging.logger import logging
from networksecurity.pipeline.training_pipeline import TrainingPipeline
from networksecurity.utils.main_utils.utils import load_object
from networksecurity.utils.ml_utils.model.estimator import NetworkModel
from networksecurity.constants.training_pipeline import DATA_INGESTION_COLLECTION_NAME
from networksecurity.constants.training_pipeline import DATA_INGESTION_DATABASE_NAME

database = client[DATA_INGESTION_DATABASE_NAME]
collection = database[DATA_INGESTION_COLLECTION_NAME]

from fastapi import FastAPI, File, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from uvicorn import run as app_run

app = FastAPI()
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="./templates")

# --- 2. NEW FUNCTION: Download Model from Cloudflare R2 ---
def sync_model_from_s3():
    """
    Downloads the 'final_model' folder from Cloudflare R2 to the local container.
    """
    try:
        bucket_name = os.getenv("TRAINING_BUCKET_NAME")
        s3_endpoint = os.getenv("S3_ENDPOINT_URL")
        
        # Connect to Cloudflare R2 using boto3
        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            endpoint_url=s3_endpoint
        )
        
        logging.info("Attempting to download final_model from Cloudflare R2...")

        # Ensure local directory exists
        os.makedirs("final_model", exist_ok=True)

        # List files in the 'final_model' folder on S3/R2
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix="final_model/")
        
        if 'Contents' in response:
            for obj in response['Contents']:
                file_key = obj['Key'] # e.g., final_model/model.pkl
                if file_key.endswith('/'): continue # skip folders
                
                local_file_path = file_key
                
                # Download the file
                logging.info(f"Downloading {file_key}...")
                s3_client.download_file(bucket_name, file_key, local_file_path)
                
            logging.info("Model download completed successfully.")
        else:
            logging.warning("No model found in Cloudflare bucket. Please run /train first.")
            
    except Exception as e:
        logging.error(f"Error downloading model from Cloudflare: {e}")

# --- 3. STARTUP EVENT: Run the download automatically ---
@app.on_event("startup")
async def startup_event():
    """
    When the app starts, this runs automatically to fetch your model.
    """
    sync_model_from_s3()

# --- 4. Routes ---
@app.get("/", tags=["authentication"])
async def index():
    return RedirectResponse(url="/docs")

@app.get("/train")
async def train_route():
    try:
        train_pipeline = TrainingPipeline()
        train_pipeline.run_pipeline()
        return Response("Training is successfully completed")
    except Exception as e:
        raise NetworkSecurityException(e, sys)

@app.post("/predict")
async def predict_route(request: Request, file: UploadFile = File(...)):
    try:
        # Create output directory if it doesn't exist yet
        os.makedirs("prediction_output", exist_ok=True)

        df = pd.read_csv(file.file)
        
        # Load Model (These files should now exist thanks to startup_event)
        preprocessor = load_object("final_model/preprocessor.pkl")
        final_model = load_object("final_model/model.pkl")
        
        network_model = NetworkModel(preprocessor=preprocessor, model=final_model)
        
        # Predict
        y_pred = network_model.predict(df)
        df['predicted_column'] = y_pred
        
        # Save output
        df.to_csv('prediction_output/output.csv')
        
        # Render Table
        table_html = df.to_html(classes='table table-striped')
        return templates.TemplateResponse("table.html", {"request": request, "table": table_html})
        
    except Exception as e:
        raise NetworkSecurityException(e, sys)

# --- 5. HOST & PORT CONFIGURATION ---
if __name__ == "__main__":
    # Hugging Face Spaces REQUIRES port 7860
    app_run(app, host="0.0.0.0", port=8000)
