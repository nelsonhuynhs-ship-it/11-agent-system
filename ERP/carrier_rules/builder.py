"""Build carrier rules JSON for all carriers from GW_Raw data."""
import sys, json, os
sys.stdout.reconfigure(encoding='utf-8')

OUTPUT_DIR = r'd:\NELSON\2. Areas\PricingSystem\Engine_test\ERP\config\carrier_rules'
os.makedirs(OUTPUT_DIR, exist_ok=True)

def save(name, data):
    path = os.path.join(OUTPUT_DIR, f'{name}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f'  ✅ {name}.json saved')

# ═══════════════════════════════════════════════════════════════
# COSCO
# ═══════════════════════════════════════════════════════════════
cosco = {
    "carrier": "COSCO",
    "carrier_full_name": "COSCO Shipping Lines",
    "updated": "2024-04-28",
    "source_files": ["COSCO Weight Limit(20240428).xlsx"],
    "gross_weight": {
        "US": {
            "base_port_cy": {
                "description": "Port-to-port cargo at base port CY",
                "limits_kgs": {"20GP": "Max Payload", "40GP": "Max Payload", "40HQ": "Max Payload", "45GP": "Max Payload"},
                "ows_charge": "OWP USD100/UNIT if 20GP > 19,976 KGS"
            },
            "ipi_via_wc": {
                "description": "IPI to Inland CY via US West Coast",
                "limits_kgs": {"20GP": 19976, "40GP": 19976, "40HQ": 19976, "45GP": 19976},
                "ows_charge": "OWR USD200/20GP if net weight 17,252 < W ≤ 19,976 KGS"
            },
            "ipi_via_tacoma": {
                "description": "IPI to Inland CY via Tacoma (on-dock EB)",
                "limits_kgs": {"20GP": 21500, "40GP": 25000, "40HQ": 25000, "45GP": 25000},
                "ows_charge": "OWR USD200/20GP if net weight 17,252 < W ≤ 21,500 KGS"
            },
            "ipi_via_prr": {
                "description": "IPI to Inland CY via Prince Rupert",
                "limits_kgs": {"20GP": 21700, "40GP": 27000, "40HQ": 27000, "45GP": 27000},
                "note": "Exceeding 21,700 KGS requires carrier approval"
            },
            "ipi_via_van": {
                "description": "IPI to Inland CY via Vancouver (OPNW/EPNW)",
                "limits_kgs": {"20GP": 21700, "40GP": 27000, "40HQ": 27000, "45GP": 27000},
                "ows_charge": "OWP USD100/UNIT if 20GP > 19,976 KGS"
            },
            "ripi_via_ec": {
                "description": "RIPI to Inland CY via NYC/SAV/ORF/MOB",
                "limits_kgs": {"20GP": 21500, "40GP": 25000, "40HQ": 25000, "45GP": 25000},
                "ows_charge": "OWR USD200/20GP if net weight 17,252 < W"
            },
            "ripi_via_hou": {
                "description": "RIPI to Inland CY via Houston",
                "limits_kgs": {"20GP": 19976, "40GP": 19976, "40HQ": 19976, "45GP": 19976},
                "ows_charge": "OWR USD200/20GP if net weight 17,252 < W"
            },
            "ripi_via_hal": {
                "description": "RIPI to Inland CY via Halifax",
                "limits_kgs": {"20GP": 21700, "40GP": 27000, "40HQ": 27000, "45GP": 27000},
                "note": "Exceeding 21,700 KGS requires carrier approval"
            },
            "door_delivery": {
                "description": "Door delivery cargo",
                "limits_kgs": {"20GP": 19976, "40GP": 19976, "40HQ": 19976, "45GP": 19976},
                "ows_charge": "OWR USD200/20GP if net weight 17,252 < W"
            }
        }
    },
    "ows_charges": {
        "US": {
            "owc_truck": {"amount": 250, "currency": "USD", "per": "unit", "mode": "CY via Truck"},
            "owc_door_truck": {"amount": 250, "currency": "USD", "per": "unit", "mode": "Door via Truck"},
            "owr_cy_rail": {"amount": 200, "currency": "USD", "per": "unit", "mode": "CY via Rail"},
            "owr_door_truck_rail": {"amount": 450, "currency": "USD", "per": "unit", "mode": "Door via Truck+Rail"},
            "owr_cy_rail_heavy": {"amount": 450, "currency": "USD", "per": "unit", "mode": "CY via Rail (transload)"},
            "port_to_port": {"amount": 0, "note": "No OWS for port-to-port cargo"},
            "threshold_20gp_kgs": 17252,
            "note": "OWC = inland via Truck, OWR = inland via Rail"
        }
    }
}
save("COSCO", cosco)

# ═══════════════════════════════════════════════════════════════
# YML
# ═══════════════════════════════════════════════════════════════
yml = {
    "carrier": "YML",
    "carrier_full_name": "Yang Ming Line",
    "updated": "2024",
    "source_files": ["YML -Cargo_Weight_Limitation.xlsx"],
    "gross_weight": {
        "CA": {
            "quebec_door": {
                "description": "Province of Quebec Door Service",
                "limits_lbs": {"20GP": 47500, "40GP": 50000, "40HQ": 50000, "45GP": 50000},
                "limits_kgs": {"20GP": 21546, "40GP": 22680, "40HQ": 22680, "45GP": 22680}
            },
            "canada_door": {
                "description": "Canada Door Service (general)",
                "limits_lbs": {"20GP": 47500, "40GP": 55000, "40HQ": 55000, "45GP": 55000},
                "limits_kgs": {"20GP": 21546, "40GP": 24948, "40HQ": 24948, "45GP": 24948}
            },
            "cy_cp_rail": {
                "description": "Canada CY via CP Rail",
                "limits_lbs": {"20GP": 47500, "40GP": 58000, "40HQ": 58000, "45GP": 58000},
                "limits_kgs": {"20GP": 21546, "40GP": 26308, "40HQ": 26308, "45GP": 26308}
            },
            "cy_cn_rail": {
                "description": "Canada CY via CN Rail",
                "limits_lbs": {"20GP": 47900, "40GP": 60000, "40HQ": 60000, "45GP": 60000},
                "limits_kgs": {"20GP": 21727, "40GP": 27216, "40HQ": 27216, "45GP": 27216}
            },
            "cy_cp_rail_heavy": {
                "description": "Canada CY via CP Rail - Heavy Weight",
                "limits_lbs": {"20GP": 54000, "40GP": 60000, "40HQ": 60000, "45GP": 60000},
                "limits_kgs": {"20GP": 24494, "40GP": 27216, "40HQ": 27216, "45GP": 27216}
            },
            "cy_cn_rail_heavy": {
                "description": "Canada CY via CN Rail - Heavy Weight",
                "limits_lbs": {"20GP": 55000, "40GP": 65000, "40HQ": 65000, "45GP": 65000},
                "limits_kgs": {"20GP": 24948, "40GP": 29484, "40HQ": 29484, "45GP": 29484}
            },
            "notes": [
                "During Canadian Spring Thaw period, weight limits may be reduced",
                "For US cargo moving via Canada, check specific routing requirements"
            ]
        },
        "US": {
            "rail_limits": {
                "ns_rail": {"20GP_lbs": 44000, "40GP_lbs": 52000, "45GP_lbs": 52000, "note": "NS Rail standard"},
                "ns_rail_heavy": {"20GP_lbs": 47500, "40GP_lbs": 58000, "45GP_lbs": 55500, "note": "NS Rail Heavy Load"},
                "csx_rail": {"20GP_lbs": 48000, "40GP_lbs": 58000, "45GP_lbs": 58000},
                "bnsf_rail": {"20GP_lbs": 48000, "40GP_lbs": 58000, "45GP_lbs": 58000},
                "up_rail": {"20GP_lbs": 48000, "40GP_lbs": 58000, "45GP_lbs": 58000},
                "portland_nwcs": {"20GP_lbs": 39050, "40GP_lbs": 44000, "45GP_lbs": 44000},
                "portland_nwcs_heavy": {"20GP_lbs": 48000, "40GP_lbs": 58000, "45GP_lbs": 58000}
            },
            "state_limits_available": True,
            "note": "Per-state GVW and cargo weight limits available — refer to source file"
        }
    }
}
save("YML", yml)

# ═══════════════════════════════════════════════════════════════
# ZIM
# ═══════════════════════════════════════════════════════════════
zim = {
    "carrier": "ZIM",
    "carrier_full_name": "ZIM Integrated Shipping",
    "updated": "2024",
    "source_files": ["OWS ZIM.xlsx"],
    "gross_weight": {
        "US": {
            "rail_via_lax": {
                "description": "Rail weight limitation ex USLAX to inland",
                "limits_lbs": {"20GP": 38000, "40GP": 44000, "40HQ": 44000}
            }
        }
    },
    "ows_charges": {
        "US": {
            "tier_1": {
                "charge": 200, "currency": "USD", "per": "20GP",
                "condition": "Net weight between 17,252 KGS and 19,958 KGS"
            },
            "tier_2": {
                "charge": 350, "currency": "USD", "per": "20GP",
                "condition": "Net weight over 19,958 KGS"
            },
            "note": "Per service contract terms"
        },
        "CA_via_vancouver_prr": {
            "cn_rail_ows": {
                "20GP": {"charge": 600, "condition": "Net weight 21,727-24,948 KGS"},
                "40GP_45GP": {"charge": 390, "condition": "Net weight 27,216-29,484 KGS"}
            }
        },
        "CA_via_halifax": {
            "cn_rail_ows": {
                "20GP": {"charge": 390, "condition": "Net weight 21,727-24,948 KGS"},
                "40GP_45GP": {"charge": 390, "condition": "Net weight 27,216-29,484 KGS"}
            }
        }
    }
}
save("ZIM", zim)

# ═══════════════════════════════════════════════════════════════
# HPL (Hapag-Lloyd)
# ═══════════════════════════════════════════════════════════════
hpl = {
    "carrier": "HPL",
    "carrier_full_name": "Hapag-Lloyd",
    "updated": "2024",
    "source_files": ["HPL Canada_Intermodal_Weights.xlsx", "HPL RNA_Inland-Overweight_Guide.pdf"],
    "gross_weight": {
        "CA": {
            "via_halifax_cn_rail": {
                "description": "Import via Halifax CN Rail to Canada/US inland",
                "standard_limits_kgs": {
                    "20GP": 21727,
                    "40GP": 27216,
                    "40HQ": 27216
                },
                "overweight_range_kgs": {
                    "20GP": "21,728 - 24,947",
                    "40GP": "27,217 - 29,484",
                    "40HQ": "27,217 - 29,484"
                },
                "destinations": [
                    "Montreal", "Toronto", "Winnipeg", "Saskatoon",
                    "Calgary", "Edmonton", "Vancouver",
                    "Chicago", "Detroit", "Indianapolis"
                ],
                "note": "OW surcharge applies for weights in overweight range"
            }
        },
        "US": {
            "note": "Refer to HPL RNA Inland-Overweight Guide PDF for US weight limits"
        }
    }
}
save("HPL", hpl)

# ═══════════════════════════════════════════════════════════════
# MSC
# ═══════════════════════════════════════════════════════════════
msc = {
    "carrier": "MSC",
    "carrier_full_name": "Mediterranean Shipping Company",
    "updated": "2025",
    "source_files": ["MSC usa_rail_info_2025.xlsx", "MSC canada_weight_restrictions.pdf"],
    "gross_weight": {
        "US": {
            "on_dock": {
                "description": "ON-DOCK Rail CY cargo",
                "limits_lbs": {"20GP": 47840, "40GP": 58450, "40HQ": 58450},
                "limits_kgs": {"20GP": 21700, "40GP": 26512, "40HQ": 26512},
                "note": "Standard on-dock weight, no OWS surcharge"
            },
            "off_dock": {
                "description": "OFF-DOCK Rail CY cargo (truck move involved)",
                "standard_lbs": {"20GP": 38200, "40GP": 44000, "40HQ": 44000},
                "max_with_surcharge_lbs": {"20GP": 44000, "40GP": "N/A", "40HQ": "N/A"},
                "note": "20GP can go up to 44,000 lbs with triaxle/overweight surcharge"
            },
            "routing_detail": "Detailed per-ramp ON/OFF dock data available (6 sheets: EC/WC Import/Export)"
        },
        "CA": {
            "note": "Refer to MSC canada_weight_restrictions.pdf"
        }
    }
}
save("MSC", msc)

# ═══════════════════════════════════════════════════════════════
# HMM
# ═══════════════════════════════════════════════════════════════
hmm = {
    "carrier": "HMM",
    "carrier_full_name": "HMM (Hyundai Merchant Marine)",
    "updated": "2024",
    "source_files": ["HMM USCA Rail Weight limitation Guideline (Ver.1).xlsx"],
    "gross_weight": {
        "US": {
            "routing_available": True,
            "routes": {
                "via_lalb": "Detailed per-destination limits (DC, RF, SR types)",
                "via_nyc": "Detailed per-destination limits (DC, RF types)",
                "via_other_us": "Detailed per-destination limits (DC, RF, RD types)"
            },
            "note": "HMM has 22 detailed sheets with per-destination, per-container-type limits"
        },
        "CA": {
            "routing_available": True,
            "routes": {
                "via_ca_terminals": "Detailed per-destination limits (DC, RF types)"
            }
        }
    },
    "special_equipment": {
        "available": True,
        "types": ["Flexi-tanks", "Tanks", "Flat Rack", "Open Top", "SR (Super Rack)"]
    }
}
save("HMM", hmm)

# ═══════════════════════════════════════════════════════════════
# EMC (Evergreen)
# ═══════════════════════════════════════════════════════════════
emc = {
    "carrier": "EMC",
    "carrier_full_name": "Evergreen Marine Corporation",
    "updated": "2024",
    "source_files": ["EMC OWS.txt"],
    "gross_weight": {
        "US": {
            "base_port": {"note": "Follow booking note for base port limits"},
            "inland": {"note": "Check case by case with salesline for inland weight limits"}
        }
    },
    "ows_charges": {
        "note": "No fixed OWS schedule — check case-by-case with EMC salesline"
    }
}
save("EMC", emc)

# ═══════════════════════════════════════════════════════════════
# MSK (Maersk)
# ═══════════════════════════════════════════════════════════════
msk = {
    "carrier": "MSK",
    "carrier_full_name": "Maersk Line",
    "updated": "2024-11",
    "source_files": ["MSK local-charges-nam-15-11-2024.pdf"],
    "gross_weight": {
        "note": "Data in PDF format — local charges North America. Needs manual extraction."
    },
    "ows_charges": {
        "note": "Refer to MSK local charges PDF for OWS rates"
    }
}
save("MSK", msk)

print(f'\n✅ All carrier rules created in: {OUTPUT_DIR}')
print(f'   Total: {len(os.listdir(OUTPUT_DIR))} files')
