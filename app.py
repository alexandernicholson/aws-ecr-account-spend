import boto3
import json
import requests

def get_regions():
    ec2 = boto3.client('ec2')
    regions = [region['RegionName'] for region in ec2.describe_regions()['Regions']]
    return regions

def get_repo_details(ecr_client):
    paginator = ecr_client.get_paginator('describe_repositories')
    for page in paginator.paginate():
        for repo in page['repositories']:
            yield repo['repositoryName']

def get_image_details(ecr_client, repository_name):
    paginator = ecr_client.get_paginator('describe_images')
    for page in paginator.paginate(repositoryName=repository_name):
        for image in page['imageDetails']:
            yield image

def get_price_per_gb(region):
    # Define the URL for the AWS Price List API for Amazon ECR
    url = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonECR/current/index.json"
    response = requests.get(url)
    pricing_data = response.json()

    # Assuming the pricing structure includes a 'Terms' section under 'OnDemand'
    for sku, offers in pricing_data['terms']['OnDemand'].items():
        if pricing_data['products'][sku]['attributes']['location'] == region:
            details = list(offers.values())[0]['priceDimensions']
            for price_dimension in details.values():
                if 'per GB' in price_dimension['description']:
                    return float(price_dimension['pricePerUnit']['USD'])

    # Default price if region-specific pricing is not found
    return 0.10  # Default to 10 cents as a fallback

def calculate_costs():
    regions_costs = []
    regions = get_regions()

    for region in regions:
        ecr_client = boto3.client('ecr', region_name=region)
        print(f"\033[96mProcessing Region: {region}\033[0m")  # Cyan color
        region_cost = 0
        repos_costs = []

        price_per_gb = get_price_per_gb(region)  # Get dynamic pricing per region

        try:
            for repository_name in get_repo_details(ecr_client):
                image_count = 0
                total_storage_gb = 0

                for image in get_image_details(ecr_client, repository_name):
                    image_count += 1
                    total_storage_gb += image.get('imageSizeInBytes', 0) / (1024**3)

                repo_cost = total_storage_gb * price_per_gb
                region_cost += repo_cost
                repos_costs.append((repository_name, image_count, total_storage_gb, repo_cost))

            # Sorting repositories by cost in descending order
            repos_costs.sort(key=lambda x: x[3], reverse=True)
            regions_costs.append((region, region_cost, repos_costs))
        except Exception as e:
            print(f"Error processing region {region}: {str(e)}")

    # Sorting regions by total cost in descending order
    regions_costs.sort(key=lambda x: x[1], reverse=True)

    return regions_costs

def format_cost(cost):
    if cost >= 100:
        return f"\033[91m${cost:.2f}\033[0m"  # Red
    elif cost >= 50:
        return f"\033[93m${cost:.2f}\033[0m"  # Orange
    elif cost > 0:
        return f"\033[92m${cost:.2f}\033[0m"  # Green
    else:
        return f"\033[97m${cost:.2f}\033[0m"  # White

def main():
    regions_costs = calculate_costs()
    for region, region_cost, repos_costs in regions_costs:
        print(f"\n\033[95mRegion: {region}, Total Region Cost: {format_cost(region_cost)}\033[0m")  # Magenta color
        for repo in repos_costs:
            formatted_cost = format_cost(repo[3])
            print(f"Repository: {repo[0]}, Images: {repo[1]}, Storage: {repo[2]:.2f} GB, Cost: {formatted_cost}")

if __name__ == '__main__':
    main()