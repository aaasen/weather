#!/bin/bash
gcloud run deploy denali-wx --source . --region us-west1 --allow-unauthenticated --platform managed
