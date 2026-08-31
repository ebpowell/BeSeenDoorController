
            CREATE TABLE IF NOT EXISTS key_fobs.reservation_blocks (
                block_id SERIAL PRIMARY KEY,
                block_key VARCHAR(50) UNIQUE NOT NULL,
                block_name VARCHAR(100) NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                display_order INT DEFAULT 1,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

                INSERT INTO key_fobs.reservation_blocks (block_key, block_name, start_time, end_time, display_order) VALUES
                ('block1', 'Block 1: Morning', '08:00:00', '12:00:00', 1),
                ('block2', 'Block 2: Afternoon', '13:00:00', '17:00:00', 2),
                ('block3', 'Block 3: Evening', '18:00:00', '23:00:00', 3)
                ON CONFLICT (block_key) DO NOTHING;
              
                CREATE TABLE IF NOT EXISTS key_fobs.reservation_fee_config (
                    config_key VARCHAR(50) PRIMARY KEY,
                    fee_amount DECIMAL(10,2) NOT NULL,
                    description TEXT,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
           
                INSERT INTO key_fobs.reservation_fee_config (config_key, fee_amount, description) VALUES
                ('single_block_fee', 15.00, 'Fee for reserving a single time block'),
                ('multi_block_fee', 30.00, 'Flat rate fee for reserving 2 or 3 time blocks')
                ON CONFLICT (config_key) DO NOTHING;
           
                CREATE TABLE IF NOT EXISTS key_fobs.clubhouse_deposits (
                    deposit_id SERIAL PRIMARY KEY,
                    property_id INT NOT NULL REFERENCES key_fobs.properties(property_id) ON DELETE CASCADE,
                    reservation_id INT,
                    amount DECIMAL(10,2) NOT NULL DEFAULT 150.00,
                    deposit_status VARCHAR(30) NOT NULL DEFAULT 'On File',
                    deposit_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    date_added DATE NOT NULL DEFAULT CURRENT_DATE,
                    check_or_ref_no VARCHAR(100),
                    received_by VARCHAR(100),
                    refund_date DATE,
                    notes TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );

                ALTER TABLE key_fobs.clubhouse_deposits ADD COLUMN IF NOT EXISTS date_added DATE DEFAULT CURRENT_DATE;
                ALTER TABLE key_fobs.clubhouse_reservations ADD COLUMN IF NOT EXISTS deposit_added_date DATE;

               