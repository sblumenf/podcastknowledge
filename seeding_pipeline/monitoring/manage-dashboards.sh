#!/bin/bash

# Dashboard management script for Podcast KG monitoring

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DASHBOARDS_DIR="${SCRIPT_DIR}/grafana/dashboards"
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASS="${GRAFANA_PASS:-admin}"

function usage() {
    echo "Usage: $0 {import|export|validate} [dashboard-name]"
    echo ""
    echo "Commands:"
    echo "  import    Import dashboards to Grafana"
    echo "  export    Export dashboards from Grafana"
    echo "  validate  Validate dashboard JSON files"
    echo ""
    echo "Examples:"
    echo "  $0 import                    # Import all dashboards"
    echo "  $0 import podcast-kg-pipeline # Import specific dashboard"
    echo "  $0 export podcast-kg-slo     # Export specific dashboard"
    echo "  $0 validate                  # Validate all dashboards"
}

function validate_dashboard() {
    local dashboard_file=$1
    echo "Validating ${dashboard_file}..."
    
    # Check if file exists
    if [ ! -f "${dashboard_file}" ]; then
        echo "ERROR: Dashboard file not found: ${dashboard_file}"
        return 1
    fi
    
    # Validate JSON syntax
    if ! jq empty "${dashboard_file}" 2>/dev/null; then
        echo "ERROR: Invalid JSON in ${dashboard_file}"
        return 1
    fi
    
    # Check required fields
    local title=$(jq -r '.title' "${dashboard_file}")
    local uid=$(jq -r '.uid' "${dashboard_file}")
    
    if [ "${title}" == "null" ] || [ -z "${title}" ]; then
        echo "ERROR: Dashboard title missing in ${dashboard_file}"
        return 1
    fi
    
    if [ "${uid}" == "null" ] || [ -z "${uid}" ]; then
        echo "ERROR: Dashboard UID missing in ${dashboard_file}"
        return 1
    fi
    
    echo "✓ Dashboard '${title}' (UID: ${uid}) is valid"
    return 0
}

function import_dashboard() {
    local dashboard_file=$1
    local dashboard_name=$(basename "${dashboard_file}" .json)
    
    echo "Importing dashboard: ${dashboard_name}..."
    
    # Read and prepare dashboard JSON
    local dashboard_json=$(cat "${dashboard_file}")
    
    # Create import payload
    local import_payload=$(jq -n \
        --argjson dashboard "${dashboard_json}" \
        '{
            dashboard: $dashboard,
            overwrite: true,
            inputs: [],
            folderId: 0
        }')
    
    # Import dashboard
    local response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -H "Authorization: Basic $(echo -n ${GRAFANA_USER}:${GRAFANA_PASS} | base64)" \
        -d "${import_payload}" \
        "${GRAFANA_URL}/api/dashboards/import")
    
    # Check response
    if echo "${response}" | jq -e '.imported' > /dev/null 2>&1; then
        echo "✓ Successfully imported dashboard: ${dashboard_name}"
        echo "  URL: ${GRAFANA_URL}$(echo ${response} | jq -r '.importedUrl')"
    else
        echo "ERROR: Failed to import dashboard: ${dashboard_name}"
        echo "${response}" | jq '.'
        return 1
    fi
}

function export_dashboard() {
    local dashboard_uid=$1
    
    echo "Exporting dashboard with UID: ${dashboard_uid}..."
    
    # Get dashboard
    local response=$(curl -s -X GET \
        -H "Authorization: Basic $(echo -n ${GRAFANA_USER}:${GRAFANA_PASS} | base64)" \
        "${GRAFANA_URL}/api/dashboards/uid/${dashboard_uid}")
    
    # Check response
    if echo "${response}" | jq -e '.dashboard' > /dev/null 2>&1; then
        local dashboard=$(echo "${response}" | jq '.dashboard')
        local title=$(echo "${dashboard}" | jq -r '.title')
        local filename="${DASHBOARDS_DIR}/${dashboard_uid}.json"
        
        # Clean up dashboard for export
        local clean_dashboard=$(echo "${dashboard}" | jq 'del(.id, .version)')
        
        # Save to file
        echo "${clean_dashboard}" | jq '.' > "${filename}"
        echo "✓ Successfully exported dashboard '${title}' to ${filename}"
    else
        echo "ERROR: Failed to export dashboard with UID: ${dashboard_uid}"
        echo "${response}" | jq '.'
        return 1
    fi
}

# Main script logic
case "$1" in
    import)
        if [ -z "$2" ]; then
            # Import all dashboards
            for dashboard in ${DASHBOARDS_DIR}/*.json; do
                if [ -f "${dashboard}" ]; then
                    validate_dashboard "${dashboard}" && import_dashboard "${dashboard}"
                fi
            done
        else
            # Import specific dashboard
            dashboard_file="${DASHBOARDS_DIR}/$2.json"
            validate_dashboard "${dashboard_file}" && import_dashboard "${dashboard_file}"
        fi
        ;;
        
    export)
        if [ -z "$2" ]; then
            echo "ERROR: Dashboard UID required for export"
            usage
            exit 1
        fi
        export_dashboard "$2"
        ;;
        
    validate)
        if [ -z "$2" ]; then
            # Validate all dashboards
            for dashboard in ${DASHBOARDS_DIR}/*.json; do
                if [ -f "${dashboard}" ]; then
                    validate_dashboard "${dashboard}"
                fi
            done
        else
            # Validate specific dashboard
            dashboard_file="${DASHBOARDS_DIR}/$2.json"
            validate_dashboard "${dashboard_file}"
        fi
        ;;
        
    *)
        usage
        exit 1
        ;;
esac