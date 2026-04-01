# -*- coding: utf-8 -*-
"""
data_lake.py — AI Brain Layer: DuckDB Data Lake
================================================
Single in-process analytical database that aggregates:
  - Parquet freight rates (19,700 records)
  - ERP Quotes history
  - ERP Active Jobs
  - Customer CRM profiles

Uses DuckDB for blazing-fast SQL analytics without a server.
All ML modules query this layer instead of raw Parquet/Excel.

Usage:
    from data_lake import DataLake
    lake = DataLake()
    lake.initialize(parquet_path, erp_quotes, erp_jobs, erp_customers)
    results = lake.query("SELECT * FROM win_loss_mv WHERE customer='HML'")
"""
import logging
import os
from datetime import datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# DuckDB optional import — graceful fallback to pandas
try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False
    logger.warning("[DataLake] duckdb not installed — using pandas fallback. Run: pip install duckdb")


class DataLake:
    """
    In-process DuckDB data lake for AI Brain analytics.
    Falls back to pandas DataFrames if DuckDB not installed.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn = None
        self._initialized = False
        self._last_sync: Optional[datetime] = None

        # Pandas fallback DataFrames
        self._df_rates: Optional[pd.DataFrame] = None
        self._df_quotes: Optional[pd.DataFrame] = None
        self._df_jobs: Optional[pd.DataFrame] = None
        self._df_customers: Optional[pd.DataFrame] = None

    def connect(self):
        """Establish DuckDB connection."""
        if not DUCKDB_AVAILABLE:
            return False
        try:
            self._conn = duckdb.connect(self.db_path)
            logger.info(f"[DataLake] DuckDB connected: {self.db_path}")
            return True
        except Exception as e:
            logger.error(f"[DataLake] DuckDB connect failed: {e}")
            return False

    def initialize(
        self,
        parquet_df: pd.DataFrame,
        quotes: list,
        jobs: list,
        customers: list,
    ) -> bool:
        """
        Load all data sources into DuckDB tables.
        Returns True if successful.
        """
        try:
            # Store pandas fallbacks always
            self._df_rates = parquet_df.copy() if parquet_df is not None else pd.DataFrame()
            self._df_quotes = pd.DataFrame(quotes) if quotes else pd.DataFrame()
            self._df_jobs = pd.DataFrame(jobs) if jobs else pd.DataFrame()
            self._df_customers = pd.DataFrame(customers) if customers else pd.DataFrame()

            if DUCKDB_AVAILABLE and self.connect():
                self._load_tables()
                self._build_views()
                logger.info("[DataLake] DuckDB tables + views ready")
            else:
                logger.info("[DataLake] Using pandas fallback mode")

            self._initialized = True
            self._last_sync = datetime.now()
            return True

        except Exception as e:
            logger.error(f"[DataLake] initialize error: {e}")
            return False

    def _load_tables(self):
        """Load DataFrames into DuckDB tables."""
        conn = self._conn

        # Rates table (from Parquet)
        if not self._df_rates.empty:
            conn.register("_rates_df", self._df_rates)
            conn.execute("DROP TABLE IF EXISTS rates")
            conn.execute("CREATE TABLE rates AS SELECT * FROM _rates_df")
            logger.info(f"[DataLake] rates: {len(self._df_rates):,} rows")

        # Quotes table
        if not self._df_quotes.empty:
            conn.register("_quotes_df", self._df_quotes)
            conn.execute("DROP TABLE IF EXISTS quotes")
            conn.execute("CREATE TABLE quotes AS SELECT * FROM _quotes_df")
            logger.info(f"[DataLake] quotes: {len(self._df_quotes)} rows")

        # Jobs table
        if not self._df_jobs.empty:
            conn.register("_jobs_df", self._df_jobs)
            conn.execute("DROP TABLE IF EXISTS jobs")
            conn.execute("CREATE TABLE jobs AS SELECT * FROM _jobs_df")
            logger.info(f"[DataLake] jobs: {len(self._df_jobs)} rows")

        # Customers table
        if not self._df_customers.empty:
            conn.register("_customers_df", self._df_customers)
            conn.execute("DROP TABLE IF EXISTS customers")
            conn.execute("CREATE TABLE customers AS SELECT * FROM _customers_df")
            logger.info(f"[DataLake] customers: {len(self._df_customers)} rows")

    def _build_views(self):
        """Create materialized views for ML queries."""
        conn = self._conn

        try:
            # Win/Loss stats per customer + carrier + place
            conn.execute("""
                CREATE OR REPLACE VIEW win_loss_mv AS
                SELECT
                    customer,
                    carrier,
                    place,
                    COUNT(*) AS total_quotes,
                    SUM(CASE WHEN UPPER(status) = 'WIN' THEN 1 ELSE 0 END) AS wins,
                    SUM(CASE WHEN UPPER(status) = 'LOSS' THEN 1 ELSE 0 END) AS losses,
                    ROUND(
                        SUM(CASE WHEN UPPER(status)='WIN' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1
                    ) AS win_rate_pct,
                    AVG(price) AS avg_selling,
                    AVG(CASE WHEN UPPER(status)='WIN'  THEN price END) AS avg_win_price,
                    AVG(CASE WHEN UPPER(status)='LOSS' THEN price END) AS avg_loss_price
                FROM quotes
                WHERE customer IS NOT NULL AND carrier IS NOT NULL
                GROUP BY customer, carrier, place
            """)
            logger.info("[DataLake] win_loss_mv view created")

        except Exception as e:
            logger.warning(f"[DataLake] view build partial failure: {e}")

    def query(self, sql: str) -> pd.DataFrame:
        """Run SQL against DuckDB. Falls back to empty DataFrame on error."""
        if not self._initialized:
            return pd.DataFrame()
        if self._conn and DUCKDB_AVAILABLE:
            try:
                return self._conn.execute(sql).df()
            except Exception as e:
                logger.error(f"[DataLake] query error: {e}\nSQL: {sql[:200]}")
                return pd.DataFrame()
        return pd.DataFrame()

    def get_win_loss_stats(self, customer: str = None, carrier: str = None) -> pd.DataFrame:
        """Get win/loss statistics with optional filters."""
        if self._conn and DUCKDB_AVAILABLE:
            where_parts = []
            if customer:
                where_parts.append(f"UPPER(customer) LIKE '%{customer.upper()}%'")
            if carrier:
                where_parts.append(f"UPPER(carrier) LIKE '%{carrier.upper()}%'")
            where = "WHERE " + " AND ".join(where_parts) if where_parts else ""
            return self.query(f"SELECT * FROM win_loss_mv {where} ORDER BY total_quotes DESC")

        # Pandas fallback
        df = self._df_quotes.copy() if not self._df_quotes.empty else pd.DataFrame()
        if df.empty:
            return pd.DataFrame()
        if customer:
            df = df[df['customer'].astype(str).str.upper().str.contains(customer.upper(), na=False)]
        if carrier:
            df = df[df['carrier'].astype(str).str.upper().str.contains(carrier.upper(), na=False)]
        return df.groupby(['customer','carrier','place']).apply(
            lambda g: pd.Series({
                'total_quotes': len(g),
                'wins': (g['status'].str.upper() == 'WIN').sum(),
                'win_rate_pct': round((g['status'].str.upper() == 'WIN').mean() * 100, 1),
                'avg_win_price': g.loc[g['status'].str.upper()=='WIN','price'].mean(),
                'avg_loss_price': g.loc[g['status'].str.upper()=='LOSS','price'].mean(),
            })
        ).reset_index()

    def get_rate_benchmarks(self, place: str, carrier: str = None) -> pd.DataFrame:
        """Get market rate benchmarks for a destination."""
        df = self._df_rates.copy() if not self._df_rates.empty else pd.DataFrame()
        if df.empty:
            return pd.DataFrame()
        place_mask = df['Place'].astype(str).str.upper().str.contains(place.upper(), na=False)
        df = df[place_mask]
        if carrier:
            df = df[df['Carrier'].astype(str).str.upper().str.contains(carrier.upper(), na=False)]
        if df.empty:
            return pd.DataFrame()
        return (
            df.groupby('Carrier')['Amount']
            .agg(['min','mean','max','count'])
            .rename(columns={'min':'floor','mean':'avg','max':'ceiling','count':'rate_count'})
            .reset_index()
            .sort_values('floor')
        )

    def get_customer_order_pattern(self, customer: str) -> dict:
        """Analyze customer's ordering pattern for churn detection."""
        df = self._df_quotes.copy() if not self._df_quotes.empty else pd.DataFrame()
        if df.empty:
            return {}

        cust_mask = df['customer'].astype(str).str.upper().str.contains(customer.upper(), na=False)
        cust_df = df[cust_mask].copy()

        if cust_df.empty:
            return {'customer': customer, 'pattern': 'unknown'}

        # Convert dates
        cust_df['date'] = pd.to_datetime(cust_df['date'], errors='coerce')
        wins = cust_df[cust_df['status'].str.upper() == 'WIN'].sort_values('date')

        if len(wins) < 2:
            return {'customer': customer, 'pattern': 'insufficient_data', 'total_quotes': len(cust_df)}

        # Calculate order intervals
        intervals = wins['date'].diff().dt.days.dropna()
        avg_interval = float(intervals.mean()) if not intervals.empty else 0
        last_order = wins['date'].max()
        days_since = (datetime.now() - last_order.replace(tzinfo=None)).days if pd.notna(last_order) else 999

        return {
            'customer': customer,
            'avg_order_interval_days': round(avg_interval, 1),
            'days_since_last_order': days_since,
            'churn_ratio': round(days_since / avg_interval, 2) if avg_interval > 0 else 99,
            'total_wins': len(wins),
            'total_quotes': len(cust_df),
            'win_rate': round(len(wins) / len(cust_df) * 100, 1),
            'last_order_date': last_order.strftime('%d/%m/%Y') if pd.notna(last_order) else 'unknown',
        }

    @property
    def is_ready(self) -> bool:
        return self._initialized

    def status(self) -> str:
        rate_count = len(self._df_rates) if self._df_rates is not None else 0
        quote_count = len(self._df_quotes) if self._df_quotes is not None else 0
        job_count = len(self._df_jobs) if self._df_jobs is not None else 0
        engine = "DuckDB" if (DUCKDB_AVAILABLE and self._conn) else "Pandas"
        sync_str = self._last_sync.strftime('%H:%M') if self._last_sync else 'Never'
        return (
            f"DataLake [{engine}] | Synced: {sync_str}\n"
            f"  Rates: {rate_count:,} | Quotes: {quote_count} | Jobs: {job_count}"
        )


# Module-level singleton
_lake: Optional[DataLake] = None

def get_lake() -> DataLake:
    """Get or create the global DataLake singleton."""
    global _lake
    if _lake is None:
        _lake = DataLake()
    return _lake

def init_lake(parquet_df, quotes, jobs, customers) -> DataLake:
    """Initialize the global DataLake with all data sources."""
    global _lake
    _lake = DataLake()
    _lake.initialize(parquet_df, quotes, jobs, customers)
    return _lake
