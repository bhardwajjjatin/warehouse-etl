-- Run once as an administrator outside an explicit transaction.
-- Adjust these names to match the warehouse configuration when using prefixes.
IF DB_ID(N'staging') IS NULL EXEC(N'CREATE DATABASE [staging]');
IF DB_ID(N'edw_raw') IS NULL EXEC(N'CREATE DATABASE [edw_raw]');
IF DB_ID(N'edw') IS NULL EXEC(N'CREATE DATABASE [edw]');
