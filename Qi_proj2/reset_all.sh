#!/bin/bash

echo "=================================================="
echo "🗑️  Resetting CDC Project"
echo "=================================================="

# 1. Delete offset file
if [ -f "cdc_offset.json" ]; then
    rm cdc_offset.json
    echo "✓ Deleted offset file"
else
    echo "⚠ No offset file found (already clean)"
fi

# 2. Clear Source DB
echo ""
echo "Clearing Source DB (port 5435)..."
docker exec -i db-source psql -U postgres -d postgres << 'EOF'
TRUNCATE employees RESTART IDENTITY;
TRUNCATE emp_cdc RESTART IDENTITY;
SELECT 'Source DB cleared' AS status;
EOF

# 3. Clear Destination DB
echo ""
echo "Clearing Destination DB (port 5436)..."
docker exec -i db-destination psql -U postgres -d postgres << 'EOF'
TRUNCATE employees RESTART IDENTITY;
SELECT 'Destination DB cleared' AS status;
EOF

echo ""
echo "=================================================="
echo "✅ Reset Complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. Restart Producer (Ctrl+C, then: python3 producer.py)"
echo "  2. Consumer should keep running"
echo "  3. Test with: docker exec -i db-source psql -U postgres -d postgres << 'EOF'"
echo "     INSERT INTO employees (first_name, last_name, dob, city, salary)"
echo "     VALUES ('Test', 'User', '1990-01-01', 'Boston', 50000);"
echo "     EOF"
echo ""
