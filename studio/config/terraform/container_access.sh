#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration from your Terraform output
CLUSTER_NAME="subscr-optinist-cloud-cluster"
SERVICE_NAME="subscr-optinist-cloud-service"
ASG_NAME="subscr-optinist-asg"
SSH_KEY_PATH="./subscr-optinist-cloud-private-key.pem"
REGION="ap-northeast-1"

echo -e "${BLUE}=== OptiNiSt Container Access Script ===${NC}"
echo

# Function to check if AWS CLI is configured
check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        echo -e "${RED}AWS CLI is not installed. Please install it first.${NC}"
        exit 1
    fi

    if ! aws sts get-caller-identity &> /dev/null; then
        echo -e "${RED}AWS CLI is not configured. Please run 'aws configure' first.${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ AWS CLI is configured${NC}"
}

# Function to get running tasks
get_running_tasks() {
    echo -e "${YELLOW}Getting running ECS tasks...${NC}"

    TASKS=$(aws ecs list-tasks \
        --cluster "$CLUSTER_NAME" \
        --service-name "$SERVICE_NAME" \
        --desired-status RUNNING \
        --region "$REGION" \
        --query 'taskArns[]' \
        --output text)

    if [ -z "$TASKS" ]; then
        echo -e "${RED}No running tasks found in service $SERVICE_NAME${NC}"
        echo "Checking if service exists..."
        aws ecs describe-services \
            --cluster "$CLUSTER_NAME" \
            --services "$SERVICE_NAME" \
            --region "$REGION" \
            --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}' \
            --output table
        return 1
    fi

    echo -e "${GREEN}Found running tasks:${NC}"
    echo "$TASKS" | tr '\t' '\n' | nl
    echo
}

# Function to get EC2 instances in ASG
get_asg_instances() {
    echo -e "${YELLOW}Getting EC2 instances in Auto Scaling Group...${NC}"

    INSTANCES=$(aws autoscaling describe-auto-scaling-groups \
        --auto-scaling-group-names "$ASG_NAME" \
        --region "$REGION" \
        --query 'AutoScalingGroups[0].Instances[?LifecycleState==`InService`].[InstanceId,PrivateIpAddress]' \
        --output text)

    if [ -z "$INSTANCES" ]; then
        echo -e "${RED}No running instances found in ASG $ASG_NAME${NC}"
        return 1
    fi

    echo -e "${GREEN}Found running instances:${NC}"
    echo "$INSTANCES" | while read instance_id private_ip; do
        echo "  Instance ID: $instance_id, Private IP: $private_ip"
    done
    echo
}

# Function to use ECS Exec (recommended)
ecs_exec_access() {
    echo -e "${BLUE}=== Option 1: Using ECS Exec (Recommended) ===${NC}"

    if ! get_running_tasks; then
        return 1
    fi

    # Get the first task ARN
    TASK_ARN=$(echo "$TASKS" | awk '{print $1}')
    TASK_ID=$(basename "$TASK_ARN")

    echo -e "${YELLOW}Connecting to task: $TASK_ID${NC}"
    echo

    # Check if session manager plugin is installed
    if ! aws ecs execute-command --version &> /dev/null; then
        echo -e "${RED}AWS CLI Session Manager plugin is not installed.${NC}"
        echo "Please install it from: https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html"
        return 1
    fi

    echo "Starting ECS exec session..."
    echo "Container name: subscr-optinist-cloud-container"
    echo

    aws ecs execute-command \
        --cluster "$CLUSTER_NAME" \
        --task "$TASK_ARN" \
        --container "subscr-optinist-cloud-container" \
        --region "$REGION" \
        --interactive \
        --command "/bin/bash"
}

# Function to use SSH + Docker exec
ssh_docker_access() {
    echo -e "${BLUE}=== Option 2: SSH to EC2 then Docker exec ===${NC}"

    if ! get_asg_instances; then
        return 1
    fi

    # Get first instance details
    INSTANCE_ID=$(echo "$INSTANCES" | awk '{print $1}' | head -n1)
    PRIVATE_IP=$(echo "$INSTANCES" | awk '{print $2}' | head -n1)

    echo -e "${YELLOW}Target instance: $INSTANCE_ID ($PRIVATE_IP)${NC}"

    # Check if SSH key exists
    if [ ! -f "$SSH_KEY_PATH" ]; then
        echo -e "${RED}SSH key not found at: $SSH_KEY_PATH${NC}"
        return 1
    fi

    # Get public IP if available, otherwise suggest SSM
    PUBLIC_IP=$(aws ec2 describe-instances \
        --instance-ids "$INSTANCE_ID" \
        --region "$REGION" \
        --query 'Reservations[0].Instances[0].PublicIpAddress' \
        --output text)

    if [ "$PUBLIC_IP" = "None" ] || [ -z "$PUBLIC_IP" ]; then
        echo -e "${YELLOW}Instance has no public IP. Use SSM Session Manager instead:${NC}"
        echo "aws ssm start-session --target $INSTANCE_ID --region $REGION"
        echo
        echo "Then once connected, run:"
        echo "  sudo docker ps  # Find container ID"
        echo "  sudo docker exec -it <container_id> /bin/bash"
        return 0
    fi

    echo -e "${GREEN}Connecting via SSH to $PUBLIC_IP...${NC}"
    echo

    # Create SSH command with docker exec
    cat << EOF
To connect, run these commands:

1. SSH to the instance:
   ssh -i "$SSH_KEY_PATH" ec2-user@$PUBLIC_IP

2. Once connected, find and enter the container:
   sudo docker ps
   sudo docker exec -it \$(sudo docker ps --filter "name=ecs-subscr-optinist-cloud-taskdef" --format "{{.ID}}") /bin/bash

Or run this one-liner:
ssh -i "$SSH_KEY_PATH" ec2-user@$PUBLIC_IP -t "sudo docker exec -it \\\$(sudo docker ps --filter 'name=ecs-subscr-optinist-cloud-taskdef' --format '{{.ID}}') /bin/bash"
EOF
}

# Function to use SSM Session Manager
ssm_session_access() {
    echo -e "${BLUE}=== Option 3: Using SSM Session Manager ===${NC}"

    if ! get_asg_instances; then
        return 1
    fi

    INSTANCE_ID=$(echo "$INSTANCES" | awk '{print $1}' | head -n1)

    echo -e "${YELLOW}Connecting to instance $INSTANCE_ID via SSM...${NC}"
    echo

    # Check if session manager plugin is installed
    if ! command -v session-manager-plugin &> /dev/null; then
        echo -e "${RED}AWS CLI Session Manager plugin is not installed.${NC}"
        echo "Please install it from: https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html"
        return 1
    fi

    echo "Starting SSM session..."
    echo "Once connected, run: sudo docker exec -it \$(sudo docker ps --filter 'name=ecs-subscr-optinist-cloud-taskdef' --format '{{.ID}}') /bin/bash"
    echo

    aws ssm start-session \
        --target "$INSTANCE_ID" \
        --region "$REGION"
}

# Function to show container status
show_container_status() {
    echo -e "${BLUE}=== Container Status Check ===${NC}"

    if get_running_tasks; then
        TASK_ARN=$(echo "$TASKS" | awk '{print $1}')
        echo -e "${YELLOW}Getting task details...${NC}"

        aws ecs describe-tasks \
            --cluster "$CLUSTER_NAME" \
            --tasks "$TASK_ARN" \
            --region "$REGION" \
            --query 'tasks[0].{Status:lastStatus,Health:healthStatus,Created:createdAt,CPU:cpu,Memory:memory}' \
            --output table

        echo
        echo -e "${YELLOW}Container details:${NC}"
        aws ecs describe-tasks \
            --cluster "$CLUSTER_NAME" \
            --tasks "$TASK_ARN" \
            --region "$REGION" \
            --query 'tasks[0].containers[0].{Name:name,Status:lastStatus,Health:healthStatus,ExitCode:exitCode}' \
            --output table
    fi

    echo
    echo -e "${YELLOW}Service status:${NC}"
    aws ecs describe-services \
        --cluster "$CLUSTER_NAME" \
        --services "$SERVICE_NAME" \
        --region "$REGION" \
        --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Pending:pendingCount}' \
        --output table
}

# Function to show helpful debugging commands
show_debug_commands() {
    echo -e "${BLUE}=== Helpful Debug Commands (run inside container) ===${NC}"
    cat << 'EOF'

Once you're inside the container, here are useful commands:

# Check application status
ps aux | grep python
netstat -tlnp | grep 8000

# Check logs
tail -f /var/log/*.log
journalctl -f

# Check environment variables
env | grep -E "(DB_|AWS_|S3_|OPTINIST_)"

# Check application files
ls -la /app/
ls -la /app/studio_data/
ls -la /app/.snakemake/

# Check connectivity
curl http://localhost:8000/health
nc -zv $DB_HOST 3306

# Check mounts
df -h
mount | grep -E "(efs|nfs)"

# Application logs
cd /app && python -c "
import os
import sys
sys.path.append('/app')
print('Python path:', sys.path)
print('Working dir:', os.getcwd())
print('App structure:')
os.system('find /app -name \"*.py\" | head -20')
"

EOF
}

# Main menu
main_menu() {
    echo -e "${BLUE}Choose an access method:${NC}"
    echo "1. ECS Exec (recommended - direct container access)"
    echo "2. SSH + Docker exec (if instance has public IP)"
    echo "3. SSM Session Manager + Docker exec"
    echo "4. Show container status"
    echo "5. Show debug commands"
    echo "6. Exit"
    echo
    read -p "Enter your choice (1-6): " choice

    case $choice in
        1) ecs_exec_access ;;
        2) ssh_docker_access ;;
        3) ssm_session_access ;;
        4) show_container_status ;;
        5) show_debug_commands ;;
        6) echo "Goodbye!"; exit 0 ;;
        *) echo -e "${RED}Invalid choice. Please try again.${NC}"; echo; main_menu ;;
    esac
}

# Main execution
main() {
    check_aws_cli
    echo

    # Show initial status
    show_container_status
    echo

    # Show menu
    main_menu
}

# Run main function
main
