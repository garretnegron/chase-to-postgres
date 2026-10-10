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
ON CONFLICT (pattern, min_spent) DO UPDATE
    SET subcategory = EXCLUDED.subcategory,
        priority    = EXCLUDED.priority;

INSERT INTO category_rules (pattern, min_spent, subcategory, priority) VALUES
    -- Income & money movement
    ('%H&R BLOCK%',             NULL, 'Other Income',          100),  -- tax refund deposit
    ('%ATM CHECK DEPOSIT%',     NULL, 'Other Income',          100),
    ('%FID BKG SVC%',           NULL, 'Savings & Investing',   100),  -- Fidelity, both directions
    ('%CAPITAL ONE%PMT%',       NULL, 'Credit Card Payment',   100),
    ('%AFFIRM%',                NULL, 'Hockey',                100),  -- ?
    ('%RUTGERS%INVOICE%',       NULL, 'Tuition & Fees',        100),  -- refund

    -- Shopping
    ('%MACY%',                  NULL, 'Clothing',              100),
    ('%EXPRESS #%',             NULL, 'Clothing',              100),
    ('%BANANAREPUBLIC%',        NULL, 'Clothing',              100),
    ('%BEST BUY%',              NULL, 'Electronics & Tech',    100),
    ('%MICRO ELECTRONIC%',      NULL, 'Electronics & Tech',    100),  -- Micro Center
    ('%DICKS SPORTING%',        NULL, 'General Shopping',      100),

    -- Hockey
    ('%PURE HOCKEY%',           NULL, 'Hockey',                100),  -- the spaced version
    ('%PRO STOCK STICKS%',      NULL, 'Hockey',                100),

    -- Travel
    ('%EXPEDIA%',               NULL, 'Flights & Lodging',     100),  -- ?
    ('%RESIDENCE INN%',         NULL, 'Flights & Lodging',     100),  -- ?

    -- Restaurants & bars
    ('%DEAR MAUD%',             NULL, 'Restaurants',           100),
    ('%KINYA%',                 NULL, 'Restaurants',           100),
    ('%YARD HOUSE%',            NULL, 'Restaurants',           100),
    ('%MCLOONES%',              NULL, 'Restaurants',           100),
    ('%JALAPENO MEXICAN%',      NULL, 'Restaurants',           100),
    ('%SQ *BROOKDALE%',         NULL, 'Restaurants',           100),  -- The Brookdale (closed)

    -- Health
    ('%ADVANCED SMILES%',       NULL, 'Medical & Pharmacy',    100),  -- dentist

    -- Gas
    ('%FUEL 4%',                NULL, 'Gas',                   100),  -- Wayne + Verona

    -- Entertainment
    ('%WELLMONT THEATER%',      NULL, 'Events & Hobbies',      100),
    ('%FANDUEL%',               NULL, 'Events & Hobbies',      100),  -- ?
    ('%HINGE%',                 NULL, 'Subscriptions',         100)
ON CONFLICT (pattern, min_spent) DO UPDATE
    SET subcategory = EXCLUDED.subcategory,
        priority    = EXCLUDED.priority;


INSERT INTO category_rules (pattern, min_spent, subcategory, priority) VALUES
    -- Fixes for holes in earlier rules
    ('%KRAUZERS%',              NULL, 'Convenience & Coffee',  100),  -- no-S spelling
    ('%ATM WITHDRAW%',          NULL, 'Cash Withdrawal',       100),  -- catches the cut-off version
    ('%BR FACTORY%',            NULL, 'Clothing',              100),  -- Banana Republic Factory

    -- Keyword rules: broad, so priority 200 (specific rules win)
    ('%DINER%',                 NULL, 'Restaurants',           200),
    ('%TAVERN%',                NULL, 'Restaurants',           200),
    ('%SUSHI%',                 NULL, 'Restaurants',           200),

    -- Restaurants & bars
    ('%CHEESECAKE%',            NULL, 'Restaurants',           100),
    ('%NAMI NORI%',             NULL, 'Restaurants',           100),
    ('%BAR ANTICIPATION%',      NULL, 'Restaurants',           100),
    ('%GRAIN HOUSE%',           NULL, 'Restaurants',           100),
    ('%JENKINSONS%',            NULL, 'Restaurants',           100),
    ('%BOARDWALK BAR%',         NULL, 'Restaurants',           100),
    ('%DOWN THE HATCH%',        NULL, 'Restaurants',           100),
    ('%HAIKU%',                 NULL, 'Restaurants',           100),
    ('%CUCINA CALANDRA%',       NULL, 'Restaurants',           100),
    ('%BAO DUMPLINGS%',         NULL, 'Restaurants',           100),
    ('%P.F.CHANG%',             NULL, 'Restaurants',           100),
    ('%FIREFORGE%',             NULL, 'Restaurants',           100),

    -- Fast food
    ('%TACO BELL%',             NULL, 'Fast Food & Takeout',   100),
    ('%STACI''S SANDWICH%',     NULL, 'Fast Food & Takeout',   100),

    -- Gas & parking
    ('%SUNOCO%',                NULL, 'Gas',                   100),
    ('%VERONA DELTA%',          NULL, 'Gas',                   100),  -- not just %DELTA%: that's an airline
    ('%RIVER STREET GARAGE%',   NULL, 'Restaurants',           50),
    ('%E-ZPASS%',               NULL, 'Tolls & Parking',       100),

    -- Hockey & events
    ('%MONTCLAIR STATE ICE%',   NULL, 'Hockey',                100),
    ('%TICKETMASTER%',          NULL, 'Events & Hobbies',      100),
    ('%PRUDENTIALCENTER%',      NULL, 'Events & Hobbies',      100),  -- Devils games
    ('%MSG CONCESSIONS%',       NULL, 'Events & Hobbies',      100),

    -- Clothing
    ('%SUITSHOP%',              NULL, 'Clothing',              100),
    ('%SOUTHERN TIDE%',         NULL, 'Clothing',              100),
    ('%DSW%',                   NULL, 'Clothing',              100),
    ('%TEEPUBLIC%',             NULL, 'Clothing',              100),

    -- Personal & health
    ('%LAUNDROMAT%',            NULL, 'Personal Care',         100),
    ('%VITAMIN SHOPPE%',        NULL, 'Fitness',               100)
ON CONFLICT (pattern, min_spent) DO UPDATE
    SET subcategory = EXCLUDED.subcategory,
        priority    = EXCLUDED.priority;