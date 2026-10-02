PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

CREATE TABLE departments (
    department_id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE,
    location TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE employees (
    employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL,
    manager_id INTEGER,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    job_title TEXT NOT NULL,
    hire_date TEXT NOT NULL,
    employment_status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_employees_department
        FOREIGN KEY (department_id) REFERENCES departments (department_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_employees_manager
        FOREIGN KEY (manager_id) REFERENCES employees (employee_id)
        ON DELETE RESTRICT,
    CONSTRAINT chk_employees_not_own_manager
        CHECK (manager_id IS NULL OR manager_id <> employee_id),
    CONSTRAINT chk_employees_status
        CHECK (employment_status IN ('active', 'on_leave', 'terminated'))
);

CREATE TABLE projects (
    project_id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL,
    project_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    start_date TEXT NOT NULL,
    end_date TEXT,
    status TEXT NOT NULL DEFAULT 'planned',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_projects_department
        FOREIGN KEY (department_id) REFERENCES departments (department_id)
        ON DELETE RESTRICT,
    CONSTRAINT chk_projects_date_range
        CHECK (end_date IS NULL OR end_date >= start_date),
    CONSTRAINT chk_projects_status
        CHECK (status IN ('planned', 'active', 'completed', 'cancelled'))
);

CREATE TABLE employee_projects (
    employee_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    project_role TEXT NOT NULL,
    assigned_on TEXT NOT NULL,
    released_on TEXT,
    allocation_pct REAL NOT NULL DEFAULT 100.0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_employee_projects PRIMARY KEY (employee_id, project_id),
    CONSTRAINT fk_employee_projects_employee
        FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_employee_projects_project
        FOREIGN KEY (project_id) REFERENCES projects (project_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_employee_projects_allocation
        CHECK (allocation_pct > 0 AND allocation_pct <= 100),
    CONSTRAINT chk_employee_projects_date_range
        CHECK (released_on IS NULL OR released_on >= assigned_on)
);

CREATE INDEX idx_employees_department_id ON employees (department_id);
CREATE INDEX idx_employees_manager_id ON employees (manager_id);
CREATE INDEX idx_projects_department_id ON projects (department_id);
CREATE INDEX idx_employee_projects_project_id ON employee_projects (project_id);

-- Sample data begins here (development/demo only).
INSERT INTO departments (department_id, department_code, name, location) VALUES
    (1, 'PEOPLE', 'People', 'New York'),
    (2, 'ENG', 'Engineering', 'Seattle'),
    (3, 'FIN', 'Finance', 'Chicago'),
    (4, 'OPS', 'Operations', 'Austin'),
    (5, 'SALES', 'Sales', 'Boston');

INSERT INTO employees (
    employee_id, department_id, manager_id, first_name, last_name,
    email, job_title, hire_date, employment_status
) VALUES
    (1, 1, NULL, 'Ava', 'Patel', 'ava.patel@example.com', 'People Director', '2018-03-12', 'active'),
    (2, 1, NULL, 'Noah', 'Kim', 'noah.kim@example.com', 'HR Manager', '2019-06-03', 'active'),
    (3, 1, NULL, 'Mia', 'Johnson', 'mia.johnson@example.com', 'Recruiter', '2021-02-15', 'active'),
    (4, 1, NULL, 'Liam', 'Garcia', 'liam.garcia@example.com', 'People Analyst', '2022-09-19', 'active'),
    (5, 2, NULL, 'Olivia', 'Chen', 'olivia.chen@example.com', 'Engineering Director', '2017-11-06', 'active'),
    (6, 2, NULL, 'Ethan', 'Brown', 'ethan.brown@example.com', 'Engineering Manager', '2019-01-21', 'active'),
    (7, 2, NULL, 'Sophia', 'Davis', 'sophia.davis@example.com', 'Software Engineer', '2020-08-10', 'active'),
    (8, 2, NULL, 'Mason', 'Wilson', 'mason.wilson@example.com', 'Data Engineer', '2021-04-05', 'active'),
    (9, 2, NULL, 'Isabella', 'Martinez', 'isabella.martinez@example.com', 'QA Engineer', '2023-01-16', 'active'),
    (10, 3, NULL, 'Lucas', 'Taylor', 'lucas.taylor@example.com', 'Finance Director', '2016-05-23', 'active'),
    (11, 3, NULL, 'Amelia', 'Anderson', 'amelia.anderson@example.com', 'Financial Analyst', '2020-10-12', 'active'),
    (12, 3, NULL, 'James', 'Thomas', 'james.thomas@example.com', 'Accountant', '2022-07-18', 'active'),
    (13, 3, NULL, 'Harper', 'Moore', 'harper.moore@example.com', 'Payroll Specialist', '2024-02-05', 'active'),
    (14, 4, NULL, 'Benjamin', 'Jackson', 'benjamin.jackson@example.com', 'Operations Director', '2017-08-14', 'active'),
    (15, 4, NULL, 'Evelyn', 'White', 'evelyn.white@example.com', 'Operations Manager', '2019-12-02', 'active'),
    (16, 4, NULL, 'Henry', 'Harris', 'henry.harris@example.com', 'Workforce Planner', '2021-06-28', 'active'),
    (17, 4, NULL, 'Abigail', 'Clark', 'abigail.clark@example.com', 'Operations Analyst', '2023-03-20', 'on_leave'),
    (18, 5, NULL, 'Alexander', 'Lewis', 'alexander.lewis@example.com', 'Sales Director', '2018-10-01', 'active'),
    (19, 5, NULL, 'Ella', 'Robinson', 'ella.robinson@example.com', 'Account Executive', '2020-03-09', 'active'),
    (20, 5, NULL, 'Daniel', 'Walker', 'daniel.walker@example.com', 'Sales Analyst', '2022-11-14', 'active');

UPDATE employees SET manager_id = 1 WHERE employee_id IN (2, 3, 4);
UPDATE employees SET manager_id = 5 WHERE employee_id IN (6, 7, 8, 9);
UPDATE employees SET manager_id = 10 WHERE employee_id IN (11, 12, 13);
UPDATE employees SET manager_id = 14 WHERE employee_id IN (15, 16, 17);
UPDATE employees SET manager_id = 18 WHERE employee_id IN (19, 20);

INSERT INTO projects (
    project_id, department_id, project_code, name, description,
    start_date, end_date, status
) VALUES
    (1, 2, 'ENG-101', 'Analytics Platform', 'Build a shared workforce analytics platform.', '2025-01-06', NULL, 'active'),
    (2, 2, 'ENG-102', 'Data Warehouse Modernization', 'Modernize analytics storage and pipelines.', '2025-02-03', NULL, 'active'),
    (3, 2, 'ENG-103', 'Employee Portal', 'Refresh the internal employee self-service portal.', '2025-04-14', NULL, 'active'),
    (4, 1, 'PEO-201', 'Retention Insights', 'Improve retention analysis and reporting.', '2025-01-20', NULL, 'active'),
    (5, 1, 'PEO-202', 'Hiring Process Review', 'Measure and improve recruiting workflows.', '2025-03-03', '2025-08-29', 'completed'),
    (6, 3, 'FIN-301', 'Budget Forecasting', 'Improve department-level budget forecasts.', '2025-02-10', NULL, 'active'),
    (7, 3, 'FIN-302', 'Payroll Controls', 'Review payroll reconciliation controls.', '2025-05-05', NULL, 'planned'),
    (8, 4, 'OPS-401', 'Workforce Scheduling', 'Improve workforce scheduling and capacity planning.', '2025-01-13', NULL, 'active'),
    (9, 5, 'SAL-501', 'Sales Territory Review', 'Evaluate sales coverage and territory design.', '2025-04-01', NULL, 'active'),
    (10, 5, 'SAL-502', 'Pipeline Reporting', 'Standardize pipeline reporting and metrics.', '2025-06-02', NULL, 'planned');

INSERT INTO employee_projects (
    employee_id, project_id, project_role, assigned_on, released_on, allocation_pct
) VALUES
    (2, 4, 'Project sponsor', '2025-01-20', NULL, 15.00),
    (3, 5, 'Recruiting lead', '2025-03-03', '2025-08-29', 60.00),
    (4, 4, 'Data analyst', '2025-01-20', NULL, 40.00),
    (5, 1, 'Executive sponsor', '2025-01-06', NULL, 10.00),
    (6, 1, 'Technical lead', '2025-01-06', NULL, 50.00),
    (7, 1, 'Frontend engineer', '2025-01-06', NULL, 70.00),
    (8, 1, 'Data engineer', '2025-01-06', NULL, 80.00),
    (8, 2, 'Pipeline engineer', '2025-02-03', NULL, 20.00),
    (9, 3, 'QA engineer', '2025-04-14', NULL, 50.00),
    (11, 6, 'Forecast analyst', '2025-02-10', NULL, 60.00),
    (12, 7, 'Controls analyst', '2025-05-05', NULL, 30.00),
    (13, 7, 'Payroll subject matter expert', '2025-05-05', NULL, 25.00),
    (15, 8, 'Operations lead', '2025-01-13', NULL, 40.00),
    (16, 8, 'Workforce planner', '2025-01-13', NULL, 70.00),
    (17, 8, 'Reporting analyst', '2025-01-13', NULL, 35.00),
    (18, 9, 'Executive sponsor', '2025-04-01', NULL, 10.00),
    (19, 9, 'Territory representative', '2025-04-01', NULL, 45.00),
    (20, 9, 'Sales analyst', '2025-04-01', NULL, 50.00),
    (7, 3, 'Application engineer', '2025-04-14', NULL, 30.00),
    (11, 4, 'People metrics analyst', '2025-01-20', NULL, 20.00);

COMMIT;