# -*- coding: utf-8 -*-
"""
dal_postgres.py — PostgreSQL Data Access Layer
=================================================
Same interface as data_access.py but backed by PostgreSQL.
Used when DATABASE_URL is configured.

All methods mirror the JSON-based DAL to enable seamless swap.
"""
import json
import logging
from datetime import datetime, date
from typing import Optional

log = logging.getLogger("nelson.db.dal")

from database.connection import (
    execute_sync,
    DEFAULT_TENANT_ID,
)


class PostgresDAL:
    """PostgreSQL-backed DAL with same interface as file-based DAL."""

    def __init__(self):
        self._tenant_id = DEFAULT_TENANT_ID

    # ── Quotes ────────────────────────────────────────────────────────────────

    def load_quotes_data(self) -> dict:
        """Load all quotes as dict format matching JSON structure."""
        rows = execute_sync("""
            SELECT * FROM quotes
            WHERE tenant_id = %s
            ORDER BY created_at DESC
        """, (self._tenant_id,))

        quotes = {}
        for row in rows:
            qid = row["id"]
            # Load carriers for this quote
            carriers = execute_sync("""
                SELECT * FROM quote_carriers WHERE quote_id = %s
            """, (qid,))

            carrier_list = []
            for c in carriers:
                carrier_list.append({
                    "carrier": c["carrier"],
                    "badge": c.get("badge", ""),
                    "transit": c.get("transit", ""),
                    "freetime": c.get("freetime", ""),
                    "containers": c.get("container_rates", {}),
                    "carrier_markup": c.get("carrier_markup", {}),
                    "note": c.get("note", ""),
                    "effective": str(c.get("effective", "")) if c.get("effective") else "",
                    "expiry": str(c.get("expiry", "")) if c.get("expiry") else "",
                })

            quotes[qid] = {
                "customer": row.get("customer", ""),
                "service_type": row.get("service_type", "CY-CY"),
                "pol": row.get("pol", ""),
                "pod": row.get("pod", ""),
                "place": row.get("place", ""),
                "routing": row.get("routing", ""),
                "status": row.get("status", "DRAFT"),
                "markup_mode": row.get("markup_mode", "global"),
                "global_markup": float(row.get("global_markup", 0)),
                "win_probability": row.get("win_probability"),
                "parent_quote_id": row.get("parent_quote_id"),
                "version": row.get("version", 1),
                "converted_shipment_id": row.get("converted_shipment_id"),
                "optional_charges": row.get("optional_charges", []),
                "charges_total": float(row.get("charges_total", 0)),
                "transit": row.get("transit", ""),
                "freetime": row.get("freetime", ""),
                "validity": row.get("validity", ""),
                "price_alerts": row.get("price_alerts", []),
                "carriers": carrier_list,
                "created_at": row["created_at"].isoformat() if row.get("created_at") else "",
                "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else "",
            }

        # Count for next ID
        counter = len(quotes)
        return {"quotes": quotes, "counter": counter}

    def save_quotes_data(self, data: dict):
        """Save quotes data — upsert quotes + carriers."""
        for qid, q in data.get("quotes", {}).items():
            self._upsert_quote(qid, q)

    def _upsert_quote(self, qid: str, q: dict):
        """Insert or update a single quote."""
        execute_sync("""
            INSERT INTO quotes (id, tenant_id, customer, service_type, pol, pod, place,
                routing, status, markup_mode, global_markup, win_probability,
                parent_quote_id, version, converted_shipment_id,
                optional_charges, charges_total, transit, freetime, validity,
                price_alerts, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                customer = EXCLUDED.customer,
                status = EXCLUDED.status,
                global_markup = EXCLUDED.global_markup,
                win_probability = EXCLUDED.win_probability,
                converted_shipment_id = EXCLUDED.converted_shipment_id,
                updated_at = EXCLUDED.updated_at
        """, (
            qid, self._tenant_id, q.get("customer"), q.get("service_type", "CY-CY"),
            q.get("pol"), q.get("pod"), q.get("place"), q.get("routing"),
            q.get("status", "DRAFT"), q.get("markup_mode", "global"),
            q.get("global_markup", 0), q.get("win_probability"),
            q.get("parent_quote_id"), q.get("version", 1),
            q.get("converted_shipment_id"),
            json.dumps(q.get("optional_charges", [])),
            q.get("charges_total", 0), q.get("transit"), q.get("freetime"),
            q.get("validity"),
            json.dumps(q.get("price_alerts", [])),
            q.get("created_at", datetime.now().isoformat()),
            q.get("updated_at", datetime.now().isoformat()),
        ), fetch=False)

        # Upsert carriers
        execute_sync("DELETE FROM quote_carriers WHERE quote_id = %s", (qid,), fetch=False)
        for carrier in q.get("carriers", []):
            execute_sync("""
                INSERT INTO quote_carriers (quote_id, carrier, badge, transit, freetime,
                    container_rates, carrier_markup, note, effective, expiry)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                qid, carrier.get("carrier"), carrier.get("badge"),
                carrier.get("transit"), carrier.get("freetime"),
                json.dumps(carrier.get("containers", {})),
                json.dumps(carrier.get("carrier_markup", {})),
                carrier.get("note"),
                carrier.get("effective") or None,
                carrier.get("expiry") or None,
            ), fetch=False)

    def get_quote(self, quote_id: str) -> Optional[dict]:
        """Get single quote by ID."""
        data = self.load_quotes_data()
        return data["quotes"].get(quote_id)

    def list_quotes(self) -> list:
        """List all quotes as list of dicts."""
        data = self.load_quotes_data()
        return list(data["quotes"].values())

    # ── Shipments ─────────────────────────────────────────────────────────────

    def load_shipment_state(self) -> dict:
        """Load shipments as dict matching JSON structure."""
        rows = execute_sync("""
            SELECT * FROM shipments
            WHERE tenant_id = %s
            ORDER BY created_at DESC
        """, (self._tenant_id,))

        shipments = {}
        for row in rows:
            sid = row["id"]
            # Load events as stage_history
            events = execute_sync("""
                SELECT event_type, payload, source, created_at
                FROM events
                WHERE entity_type = 'shipment' AND entity_id = %s
                ORDER BY created_at ASC
            """, (sid,))

            stage_history = []
            for ev in events:
                stage_history.append({
                    "stage": ev["payload"].get("to_stage", ev["event_type"]),
                    "at": ev["created_at"].strftime("%Y-%m-%d") if ev.get("created_at") else "",
                    "subject": ev["payload"].get("subject", ""),
                })

            shipments[sid] = {
                "customer": row.get("customer", ""),
                "type": row.get("service_type", "CY-CY"),
                "stage": row.get("stage", "BOOKING_PENDING"),
                "routing": row.get("routing", ""),
                "carrier": row.get("carrier", ""),
                "container": row.get("container_type", ""),
                "quantity": row.get("quantity", 1),
                "etd": str(row.get("etd", "")) if row.get("etd") else "",
                "eta": str(row.get("eta", "")) if row.get("eta") else "",
                "ata": str(row.get("ata", "")) if row.get("ata") else "",
                "selling_rate": float(row.get("selling_rate", 0)),
                "buying_rate": float(row.get("buying_rate", 0)),
                "profit": float(row.get("profit", 0)),
                "profit_margin": row.get("profit_margin", "0%"),
                "delay_count": row.get("delay_count", 0),
                "stage_history": stage_history,
                "risks": row.get("risks", []),
                "created_at": row["created_at"].strftime("%Y-%m-%d") if row.get("created_at") else "",
                "updated_at": row["updated_at"].strftime("%Y-%m-%d") if row.get("updated_at") else "",
                "last_subject": row.get("last_subject", ""),
                "last_sender": row.get("last_sender", ""),
                "source": row.get("source", "email"),
                "quote_id": row.get("source_quote_id"),
                "all_containers": row.get("all_containers", {}),
                "optional_charges": row.get("optional_charges", []),
            }

        return {"shipments": shipments}

    def save_shipment_state(self, state: dict):
        """Save shipment state — upsert shipments."""
        for sid, s in state.get("shipments", {}).items():
            self._upsert_shipment(sid, s)

    def _upsert_shipment(self, sid: str, s: dict):
        """Insert or update a single shipment."""
        execute_sync("""
            INSERT INTO shipments (id, tenant_id, source_quote_id, customer, carrier,
                routing, container_type, quantity, stage, service_type,
                etd, eta, ata, selling_rate, buying_rate, profit, profit_margin,
                delay_count, source, risks, all_containers, optional_charges,
                last_subject, last_sender, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                stage = EXCLUDED.stage,
                etd = EXCLUDED.etd,
                eta = EXCLUDED.eta,
                ata = EXCLUDED.ata,
                delay_count = EXCLUDED.delay_count,
                last_subject = EXCLUDED.last_subject,
                last_sender = EXCLUDED.last_sender,
                risks = EXCLUDED.risks,
                updated_at = EXCLUDED.updated_at
        """, (
            sid, self._tenant_id, s.get("quote_id"), s.get("customer"),
            s.get("carrier"), s.get("routing"), s.get("container"),
            s.get("quantity", 1), s.get("stage", "BOOKING_PENDING"),
            s.get("type", "CY-CY"),
            s.get("etd") or None, s.get("eta") or None, s.get("ata") or None,
            s.get("selling_rate", 0), s.get("buying_rate", 0),
            s.get("profit", 0), s.get("profit_margin", "0%"),
            s.get("delay_count", 0), s.get("source", "email"),
            json.dumps(s.get("risks", [])),
            json.dumps(s.get("all_containers", {})),
            json.dumps(s.get("optional_charges", [])),
            s.get("last_subject", ""), s.get("last_sender", ""),
            s.get("created_at", datetime.now().isoformat()),
            s.get("updated_at", datetime.now().isoformat()),
        ), fetch=False)

    # ── Events ────────────────────────────────────────────────────────────────

    def insert_event(self, entity_type: str, entity_id: str,
                     event_type: str, payload: dict,
                     source: str = "system", actor: str = "system"):
        """Insert event into events table."""
        execute_sync("""
            INSERT INTO events (tenant_id, entity_type, entity_id,
                event_type, payload, source, actor)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            self._tenant_id, entity_type, entity_id,
            event_type, json.dumps(payload), source, actor,
        ), fetch=False)

    def get_events(self, entity_type: str = None, entity_id: str = None,
                   limit: int = 50) -> list:
        """Get events with optional filters."""
        query = "SELECT * FROM events WHERE tenant_id = %s"
        params = [self._tenant_id]

        if entity_type:
            query += " AND entity_type = %s"
            params.append(entity_type)
        if entity_id:
            query += " AND entity_id = %s"
            params.append(entity_id)

        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        rows = execute_sync(query, tuple(params))
        return [dict(row) for row in rows]

    # ── Customers ─────────────────────────────────────────────────────────────

    def get_customers_raw(self) -> list:
        """Get all customers."""
        return execute_sync("""
            SELECT * FROM customers WHERE tenant_id = %s
        """, (self._tenant_id,))

    # ── Email Matches ─────────────────────────────────────────────────────────

    def save_email_match(self, match: dict):
        """Save an email match record."""
        execute_sync("""
            INSERT INTO email_matches (tenant_id, shipment_id, email_hash,
                subject, sender, matched_by, extracted_ids,
                detected_stages, detected_risks, email_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (email_hash) DO NOTHING
        """, (
            self._tenant_id,
            match.get("shipment_id"),
            match.get("email_hash"),
            match.get("subject"),
            match.get("sender"),
            match.get("matched_by"),
            json.dumps(match.get("extracted_ids", {})),
            json.dumps(match.get("detected_stages", [])),
            json.dumps(match.get("detected_risks", [])),
            match.get("email_date"),
        ), fetch=False)


# Singleton (only created when needed)
pg_dal = PostgresDAL()
