-- My spending categories. Safe to run more than once:
-- existing subcategories are skipped, new ones are added.
-- Groups follow Chase's credit card categories, plus Income and Money Movement.

INSERT INTO categories (subcategory, category, tax_relevant, is_spending) VALUES
    -- Income (not spending)
    ('Paycheck',               'Income',                false, false),
    ('Other Income',           'Income',                false, false),

    -- Food & Drink
    ('Restaurants',            'Food & Drink',          false, true),
    ('Fast Food & Takeout',    'Food & Drink',          false, true),
    ('Convenience & Coffee',   'Food & Drink',          false, true),

    -- Groceries
    ('Groceries',              'Groceries',             false, true),

    -- Gas
    ('Gas',                    'Gas',                   false, true),

    -- Automotive
    ('Tolls & Parking',        'Automotive',            false, true),
    ('Car Maintenance',        'Automotive',            false, true),
    ('Car Insurance & MVC',    'Automotive',            false, true),

    -- Travel
    ('Flights & Lodging',      'Travel',                false, true),
    ('Rideshare & Transit',    'Travel',                false, true),

    -- Home
    ('Rent',                   'Home',                  false, true),
    ('Household & Furniture',  'Home',                  false, true),

    -- Bills & Utilities
    ('Phone & Internet',       'Bills & Utilities',     false, true),
    ('Utilities',              'Bills & Utilities',     false, true),

    -- Entertainment
    ('Subscriptions',          'Entertainment',         false, true),
    ('Events & Hobbies',       'Entertainment',         false, true),
    ('Hockey',                 'Entertainment',         false, true),

    -- Shopping
    ('Clothing',               'Shopping',              false, true),
    ('Electronics & Tech',     'Shopping',              false, true),
    ('General Shopping',       'Shopping',              false, true),

    -- Health & Wellness
    ('Medical & Pharmacy',     'Health & Wellness',     true,  true),
    ('Fitness',                'Health & Wellness',     false, true),

    -- Personal
    ('Personal Care',          'Personal',              false, true),

    -- Education
    ('Tuition & Fees',         'Education',             true,  true),
    ('Books & Supplies',       'Education',             true,  true),

    -- Gifts & Donations
    ('Gifts',                  'Gifts & Donations',     false, true),
    ('Charity',                'Gifts & Donations',     true,  true),

    -- Professional Services
    ('Professional Services',  'Professional Services', false, true),

    -- Fees & Adjustments
    ('Bank Fees & Interest',   'Fees & Adjustments',    false, true),

    -- Money Movement (not spending, except cash)
    ('Transfers',              'Money Movement',        false, false),
    ('Venmo & Zelle',          'Money Movement',        false, false),
    ('Credit Card Payment',    'Money Movement',        false, false),
    ('Savings & Investing',    'Money Movement',        false, false),
    ('Loan Payment',           'Money Movement',        false, false),
    ('Cash Withdrawal',        'Money Movement',        false, true),

    -- Other
    ('Uncategorized',          'Other',                 false, true)
ON CONFLICT (subcategory) DO NOTHING;