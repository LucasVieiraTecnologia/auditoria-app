# Azure Deployment Plan for Auditoria Inteligente

## Application Overview
- **Application Type**: Streamlit web application for condominium auditing
- **Primary Purpose**: Internal financial analysis tool for ~4 users
- **Key Features**: 
  - PDF upload and processing
  - Financial data analysis and visualization
  - AI-powered insights (via OpenRouter/OpenAI)
  - User authentication
  - Interactive dashboards

## Deployment Strategy
- **Target Service**: Azure App Service on Linux
- **Deployment Method**: Containerized deployment using Docker
- **Resource Group**: auditoria-rg
- **App Service Plan**: B1 (Basic) tier - suitable for low traffic
- **Region**: East US (or user's preferred region)

## Architecture Components
1. **Azure App Service** - Hosts the Streamlit application
2. **Azure Container Registry** - Stores the Docker image
3. **Azure Application Insights** - Monitoring and logging
4. **Azure Key Vault** - Secure storage for API keys (OPENAI_API_KEY, etc.)

## Infrastructure Requirements
- **App Service**: Linux plan, B1 tier (1 vCore, 1.75 GB RAM)
- **Storage**: 
  - App Service storage for temporary files
  - Optionally Azure Blob Storage for PDF persistence
- **Networking**: 
  - Public endpoint with HTTPS
  - Access restrictions optional (can be configured later)
- **Secrets Management**: 
  - Application settings in App Service for environment variables
  - Consider Key Vault for production-grade secret management

## CI/CD Pipeline
- **Source**: Local repository (or GitHub when ready)
- **Build**: Docker image built via Azure Developer CLI (azd) or GitHub Actions
- **Deploy**: Automated deployment to App Service

## Environment Variables Required
- `OPENAI_API_KEY` or `OPENROUTER_API_KEY` - For AI features
- `APP_USERNAME` - Admin username (default: admin)
- `APP_PASSWORD` - Admin password (default: admin123)
- `APP_USERS` - Additional users in format user1:pass1,user2:pass2
- `STREAMLIT_SERVER_PORT` - Set to 8000 (App Service expects this)

## Docker Configuration
- **Base Image**: Python 3.9-slim
- **Dependencies**: Installed from requirements.txt
- **Exposed Port**: 8501 (Streamlit default, but App Service will map to 8000)
- **Startup Command**: `streamlit run app.py --server.port=8501 --server.address=0.0.0.0`

## Scalability Considerations
- Current tier (B1) supports ~4 concurrent users adequately
- Can scale up to S1 tier if needed
- Manual scaling configuration available in App Service

## Monitoring & Logging
- Azure Application Insights for performance monitoring
- Streamlit logging captured via App Service logs
- Custom logging for audit access (already implemented in logs_acesso.py)

## Security Considerations
- HTTPS enforced by App Service
- Authentication built into application
- Regular updates of base image recommended
- Consider enabling Azure App Service authentication for additional layer

## Estimated Monthly Cost
- App Service B1: ~$16-$20/month
- Application Insights: ~$5/month (based on low usage)
- Container Registry: Negligible for single image
- **Total**: ~$25/month

## Next Steps
1. Validate this plan with user
2. Generate infrastructure as code (Bicep or Terraform)
3. Create Dockerfile
4. Create azure.yaml for Azure Developer CLI
5. Validate deployment readiness
6. Deploy to Azure

---
*Status: Draft - Awaiting User Approval*