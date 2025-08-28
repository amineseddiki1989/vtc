-- VTC Application Database Schema
-- Production-ready PostgreSQL initialization

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Enum types
CREATE TYPE user_role AS ENUM ('client', 'chauffeur', 'admin');
CREATE TYPE ride_status AS ENUM ('requested', 'accepted', 'in_progress', 'completed', 'cancelled');
CREATE TYPE vehicle_type AS ENUM ('standard', 'comfort', 'premium', 'van');

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    role user_role NOT NULL DEFAULT 'client',
    is_verified BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    profile_picture TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Chauffeurs table
CREATE TABLE chauffeurs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    license_number VARCHAR(50) UNIQUE NOT NULL,
    license_expiry DATE NOT NULL,
    experience_years INTEGER DEFAULT 0,
    rating DECIMAL(3,2) DEFAULT 5.00,
    total_rides INTEGER DEFAULT 0,
    is_available BOOLEAN DEFAULT FALSE,
    current_latitude DECIMAL(10,8),
    current_longitude DECIMAL(11,8),
    last_location_update TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Vehicles table
CREATE TABLE vehicles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chauffeur_id UUID REFERENCES chauffeurs(id) ON DELETE CASCADE,
    make VARCHAR(50) NOT NULL,
    model VARCHAR(50) NOT NULL,
    year INTEGER NOT NULL,
    license_plate VARCHAR(20) UNIQUE NOT NULL,
    color VARCHAR(30) NOT NULL,
    vehicle_type vehicle_type NOT NULL DEFAULT 'standard',
    seats INTEGER DEFAULT 4,
    is_active BOOLEAN DEFAULT TRUE,
    insurance_expiry DATE NOT NULL,
    inspection_expiry DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Rides table
CREATE TABLE rides (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES users(id) ON DELETE SET NULL,
    chauffeur_id UUID REFERENCES chauffeurs(id) ON DELETE SET NULL,
    vehicle_id UUID REFERENCES vehicles(id) ON DELETE SET NULL,
    pickup_address TEXT NOT NULL,
    pickup_latitude DECIMAL(10,8) NOT NULL,
    pickup_longitude DECIMAL(11,8) NOT NULL,
    destination_address TEXT NOT NULL,
    destination_latitude DECIMAL(10,8) NOT NULL,
    destination_longitude DECIMAL(11,8) NOT NULL,
    status ride_status NOT NULL DEFAULT 'requested',
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    accepted_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    estimated_price DECIMAL(10,2),
    final_price DECIMAL(10,2),
    distance_km DECIMAL(8,2),
    duration_minutes INTEGER,
    client_rating INTEGER CHECK (client_rating >= 1 AND client_rating <= 5),
    chauffeur_rating INTEGER CHECK (chauffeur_rating >= 1 AND chauffeur_rating <= 5),
    client_comment TEXT,
    chauffeur_comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Payments table
CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ride_id UUID REFERENCES rides(id) ON DELETE CASCADE,
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'EUR',
    payment_method VARCHAR(50) NOT NULL,
    transaction_id VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending',
    processed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ride tracking table (for real-time location updates)
CREATE TABLE ride_tracking (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ride_id UUID REFERENCES rides(id) ON DELETE CASCADE,
    latitude DECIMAL(10,8) NOT NULL,
    longitude DECIMAL(11,8) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    INDEX (ride_id, timestamp)
);

-- Notifications table
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    type VARCHAR(50) DEFAULT 'info',
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_chauffeurs_user_id ON chauffeurs(user_id);
CREATE INDEX idx_chauffeurs_location ON chauffeurs(current_latitude, current_longitude);
CREATE INDEX idx_chauffeurs_available ON chauffeurs(is_available);
CREATE INDEX idx_vehicles_chauffeur_id ON vehicles(chauffeur_id);
CREATE INDEX idx_rides_client_id ON rides(client_id);
CREATE INDEX idx_rides_chauffeur_id ON rides(chauffeur_id);
CREATE INDEX idx_rides_status ON rides(status);
CREATE INDEX idx_rides_requested_at ON rides(requested_at);
CREATE INDEX idx_payments_ride_id ON payments(ride_id);
CREATE INDEX idx_notifications_user_id ON notifications(user_id);

-- Triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_chauffeurs_updated_at BEFORE UPDATE ON chauffeurs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_vehicles_updated_at BEFORE UPDATE ON vehicles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_rides_updated_at BEFORE UPDATE ON rides FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Default admin user (password: AdminVTC2024!)
INSERT INTO users (email, password_hash, first_name, last_name, phone, role, is_verified, is_active) 
VALUES (
    'admin@vtc-app.com', 
    crypt('AdminVTC2024!', gen_salt('bf')),
    'Admin', 
    'VTC', 
    '+33123456789', 
    'admin', 
    true, 
    true
);
