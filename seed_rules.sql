-- My categorization rules. Safe to run more than once.
-- pattern:   matched against the description, case-insensitive; % means "anything"
-- min_spent: optional; the rule only applies when at least this much was spent
-- priority:  when several rules match, the lowest number wins

INSERT INTO category_rules (pattern, min_spent, subcategory, priority) VALUES
    -- Income / money movement
    ('%PAYROLL%',               NULL, 'Paycheck',              100),  -- Rutgers + Robert Half
    ('%DISCOVER E-PAYMENT%',    NULL, 'Credit Card Payment',   100),
    ('%ZELLE%',                 NULL, 'Venmo & Zelle',         100),
    ('%VENMO%',                 NULL, 'Venmo & Zelle',         100),
    ('%ATM FEE%',               NULL, 'Bank Fees & Interest',  100),

    -- Convenience & coffee
    ('%KRAUSZER%',              NULL, 'Convenience & Coffee',  100),
    ('%CANTEEN VENDING%',       NULL, 'Convenience & Coffee',  100),  -- both vending companies
    ('%STARBUCKS%',             NULL, 'Convenience & Coffee',  100),
    ('%DUNKIN%',                NULL, 'Convenience & Coffee',  100),
    ('%7-ELEVEN%',              NULL, 'Convenience & Coffee',  100),
    ('%QUICK CHEK%',            NULL, 'Convenience & Coffee',  100),
    ('%KNIGHTSBRIDGE CAFE%',    NULL, 'Convenience & Coffee',  100),
    ('%LITTLE FALLS CO%',       NULL, 'Convenience & Coffee',  100),  -- Tiger Mart
    ('%CVS%',                   NULL, 'Convenience & Coffee',  100),  -- mostly snacks

    -- Wawa: $35 or more is gas, anything less is food
    ('%WAWA%',                  35,   'Gas',                    50),
    ('%WAWA%',                  NULL, 'Convenience & Coffee',  100),

    -- Fast food
    ('%MCDONALD%',              NULL, 'Fast Food & Takeout',   100),
    ('%CHICK-FIL-A%',           NULL, 'Fast Food & Takeout',   100),
    ('%BURGER KING%',           NULL, 'Fast Food & Takeout',   100),
    ('%PANDA EXPRESS%',         NULL, 'Fast Food & Takeout',   100),
    ('%CAVA%',                  NULL, 'Fast Food & Takeout',   100),

    -- Restaurants & bars
    ('%KIM''S SUSHI%',          NULL, 'Restaurants',           100),  -- '' = one apostrophe
    ('%JUST JAKES%',            NULL, 'Restaurants',           100),
    ('%HOMESTEAD BAR%',         NULL, 'Restaurants',           100),
    ('%VERONA INN%',            NULL, 'Restaurants',           100),
    ('%OFF THE WAGON%',         NULL, 'Restaurants',           100),

    -- Gas
    ('%EXXON%',                 NULL, 'Gas',                    50),  -- beats LITTLE FALLS CO
    ('%FUEL 4 WAYNE%',          NULL, 'Gas',                   100),

    -- Subscriptions
    ('%PATREON%',               NULL, 'Subscriptions',         100),
    ('%DISCORD%',               NULL, 'Subscriptions',         100),
    ('%APPLE.COM/BILL%',        NULL, 'Subscriptions',         100),
    ('%UBER *ONE%',             NULL, 'Subscriptions',          50),  -- beats %UBER%
    ('%UBER%',                  NULL, 'Rideshare & Transit',   100),

    -- Games
    ('%XBOX%',                  NULL, 'Events & Hobbies',      100),  -- FC packs, no judgment

    -- Hockey
    ('%INLINE SKATING CLUB%',   NULL, 'Hockey',                100),
    ('%CLARY ANDERSON%',        NULL, 'Hockey',                100),
    ('%PUREHOCKEY%',            NULL, 'Hockey',                100),
    ('%LIVEBARN%',              NULL, 'Hockey',                100)
ON CONFLICT (pattern, min_spent) DO NOTHING;