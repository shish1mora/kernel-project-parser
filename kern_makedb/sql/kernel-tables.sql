DROP TABLE IF EXISTS "KERNEL_MAIN" CASCADE;
DROP TABLE IF EXISTS "KERNEL_FIXES" CASCADE;

CREATE TABLE public."KERNEL_MAIN"
(
    kern_hash VARCHAR(40) NOT NULL,
    upstream_hash VARCHAR(40),
    kern_ver VARCHAR(40) NOT NULL,
    message TEXT,
    ro_created_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (kern_hash)
);

CREATE TABLE public."KERNEL_FIXES"
(
    id SERIAL PRIMARY KEY,
    kern_hash VARCHAR(40) NOT NULL,
    fixes_hash VARCHAR(40),
    UNIQUE (kern_hash, fixes_hash),
    FOREIGN KEY (kern_hash) REFERENCES public."KERNEL_MAIN" (kern_hash) ON DELETE CASCADE
);
