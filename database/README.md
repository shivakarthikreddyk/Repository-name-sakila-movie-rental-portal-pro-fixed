# Sakila database

The official MySQL 8.4 image initializes a persistent volume with the complete
Oracle Sakila sample schema and data. The SQL runs **only on an empty volume**.
Application deployments never delete the volume or reimport these files.
Changes to an existing schema require a separate, reviewed migration.

Source: https://downloads.mysql.com/docs/sakila-db.tar.gz
Installation guide: https://dev.mysql.com/doc/sakila/en/sakila-installation.html

Downloaded 2026-11-16. The upstream copyright and BSD license notices are
preserved in both SQL files and included in the database image.

SHA-256 of the downloaded archive:
`d8e848e1c7530d6f246684bdfdaeab12f744011df513bb210df0e898788af193`

The original files are saved as `init/01-schema.sql` and `init/02-data.sql`
so that MySQL imports them in the required order. Do not execute `01-schema.sql`
against an existing database: the upstream script drops and recreates `sakila`.
