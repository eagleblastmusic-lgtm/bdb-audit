# BDB Audit PRODUCT-V1 — raport częściowy

Audyt E1-E6: **NOT_COMPLETED**. NF02: **OPEN**. Import wyników: **BLOCKED**.

NF02 OPEN: brak niezależnie autoryzowanego producenta i kwalifikowanej aktywacji. Zachowaj ZIP poza historią. Przygotowanie paczek, lokalne kontrole i raport częściowy są dostępne; E1-E6 nie jest ukończone.

Lokalne komendy dowodzą wyłącznie wykonania wskazanych kontroli. Integralność receipt nie ustanawia autoryzacji producenta ani związania z kampanią. Nie są kwalifikacją ani wynikiem zewnętrznego audytora.

Kontrole ZIP poniżej mają status INSPECTED_UNTRUSTED. Ich ustalenia są nieprzyjętymi deklaracjami; zgodność bajtów i kontekstu nie dowodzi autorstwa ani prawdziwości.

```json
{
  "campaign": {
    "status": "READY_FOR_REVIEW",
    "store_path": "C:\\Projekty\\Audyty\\BDB Audit\\.product-smoke\\6937465a7a7543d6aa2286ac675d9902\\work\\campaign.sqlite",
    "campaign_id": "campaign_31fc162f11d95f1e",
    "accepted_history_cut": {
      "variant": "ACCEPTED_HISTORY_CUT",
      "governing_policy_ref": "pin:initial_governing_policy_ref",
      "governing_spec_refs": [
        "pin:initial_transition_profile_ref"
      ],
      "campaign_id": "campaign_31fc162f11d95f1e",
      "accepted_head_seq": 8,
      "accepted_head_hash": "0db694fea7bffc88a899d7fd031bd792c1b61d6034e3128f57c5617572835cab"
    },
    "workflow": {
      "status": "SUCCESS",
      "campaign_id": "campaign_31fc162f11d95f1e",
      "store_path": "C:\\Projekty\\Audyty\\BDB Audit\\.product-smoke\\6937465a7a7543d6aa2286ac675d9902\\work\\campaign.sqlite",
      "current_stage": "E1",
      "current_phase": null,
      "active_inbox": "E1",
      "accepted_lanes_count": 0,
      "total_required_lanes": 5,
      "missing_lanes": [
        "E1-A",
        "E1-B",
        "E1-C",
        "E1-D",
        "E1-E"
      ],
      "stage_complete": false,
      "phase_complete": false,
      "source_commit_sha": "f27387755f3a88af400dd930280721eebd5506fd",
      "source_tree_sha": "80ea5443b921f9471962a4a002ca3d9dd0b73346",
      "executor_profile": "ChatGPT / GitHub",
      "executor_model": "Sol 5.6"
    },
    "profile": "PRODUCT-V1_PREPARATION_AND_LOCAL_CHECKS",
    "external_ingestion": "BLOCKED",
    "nf02": "OPEN",
    "audit_completion": "NOT_COMPLETED",
    "qualification": "NO_NEW_Q1_Q2_CLAIM",
    "isolation": "DECLARED; host/network runner NOT_ENFORCED",
    "activation_blockers": [
      "INDEPENDENT_INSTALLATION_AND_PRODUCER_AUTHORITY_NOT_ESTABLISHED",
      "QUALIFIED_SUCCESSOR_SCHEMA_PROTOCOL_AND_Q1_Q2_NOT_ESTABLISHED",
      "NEW_CAMPAIGN_PRIOR_PACKAGE_BINDING_AND_STARTED_CHRONOLOGY_NOT_IMPLEMENTED"
    ],
    "next_action": "NF02 OPEN: brak niezależnie autoryzowanego producenta i kwalifikowanej aktywacji. Zachowaj ZIP poza historią. Przygotowanie paczek, lokalne kontrole i raport częściowy są dostępne; E1-E6 nie jest ukończone.",
    "packages": [
      {
        "campaign_id": "campaign_31fc162f11d95f1e",
        "stage_id": "E1",
        "lane_slot": "E1-A",
        "lane_title": "General Systems & Architecture",
        "strategy": "STRUCTURAL_ENUMERATION",
        "input_history_cut": {
          "accepted_head_hash": "5f38b2615dc2a4868f042349be8085a45e25163c75fd88b0e5dafb2e214937a3",
          "accepted_head_seq": 7,
          "campaign_id": "campaign_31fc162f11d95f1e",
          "governing_policy_ref": "pin:initial_governing_policy_ref",
          "governing_spec_refs": [
            "pin:initial_transition_profile_ref"
          ],
          "variant": "ACCEPTED_HISTORY_CUT"
        },
        "package_digest": "fc1e143e7ddbe1c082fcafbadb5dfb287c3b741b5bedd4f2bcfe8114e8015da6",
        "package_zip_path": "C:\\Projekty\\Audyty\\BDB Audit\\.product-smoke\\6937465a7a7543d6aa2286ac675d9902\\work\\artifacts\\campaign_31fc162f11d95f1e\\E1\\E1-A_General_Systems_AND_Architecture_fc1e143e7ddb_PACKAGE.zip",
        "package_zip_sha256": "7a90f19764eed8771cee9cea533f1bfe0bd73e9fed83cd40ee17ac05a171789a",
        "prompt_sha256": "cfe04ec581780cdabc7eb9780da70a58859d083ae50b193346401b1aa6611a85",
        "assignment_ref": {
          "digest_profile": "BDB-OBJECT-DIGEST-1",
          "kind": "assignment_manifest",
          "ref_class": "PRIOR_ACCEPTED_ONLY",
          "revision_digest": "cd5f42a15fe0fd889b2913a666cb29c997bf38d28b8ea88d6fb9828ac3faa4af",
          "schema_revision_ref": "BDB_SCHEMA_REGISTRY::assignment_manifest/1"
        },
        "attempt_ref": {
          "digest_profile": "BDB-OBJECT-DIGEST-1",
          "kind": "attempt",
          "ref_class": "PRIOR_ACCEPTED_ONLY",
          "revision_digest": "e99a2c33668fc4a832cb9e2e7fd10868bf8930ce0f3beb37190c9656ed1a2c61",
          "schema_revision_ref": "BDB_SCHEMA_REGISTRY::attempt/1"
        }
      },
      {
        "campaign_id": "campaign_31fc162f11d95f1e",
        "stage_id": "E1",
        "lane_slot": "E1-B",
        "lane_title": "Security, Trust & Authority",
        "strategy": "AUTHORITY_BOUNDARY_ANALYSIS",
        "input_history_cut": {
          "accepted_head_hash": "5f38b2615dc2a4868f042349be8085a45e25163c75fd88b0e5dafb2e214937a3",
          "accepted_head_seq": 7,
          "campaign_id": "campaign_31fc162f11d95f1e",
          "governing_policy_ref": "pin:initial_governing_policy_ref",
          "governing_spec_refs": [
            "pin:initial_transition_profile_ref"
          ],
          "variant": "ACCEPTED_HISTORY_CUT"
        },
        "package_digest": "af631553b88e1d9b7329628a9a97c2840644ceb226247a5130ab6801e6b6abad",
        "package_zip_path": "C:\\Projekty\\Audyty\\BDB Audit\\.product-smoke\\6937465a7a7543d6aa2286ac675d9902\\work\\artifacts\\campaign_31fc162f11d95f1e\\E1\\E1-B_Security_Trust_AND_Authority_af631553b88e_PACKAGE.zip",
        "package_zip_sha256": "a666d2ccfb4094d73004f9ce704bd060784290e9f21b8e56745e5590d261726b",
        "prompt_sha256": "e65e462b17af551d3f0600b2aaac3813e8732477e76e6e95d460f85bbf4f7626",
        "assignment_ref": {
          "digest_profile": "BDB-OBJECT-DIGEST-1",
          "kind": "assignment_manifest",
          "ref_class": "PRIOR_ACCEPTED_ONLY",
          "revision_digest": "d37a621ed169f9aa1646e81e5b6179a9430533760ddbf0b7da4786147bfd6fcd",
          "schema_revision_ref": "BDB_SCHEMA_REGISTRY::assignment_manifest/1"
        },
        "attempt_ref": {
          "digest_profile": "BDB-OBJECT-DIGEST-1",
          "kind": "attempt",
          "ref_class": "PRIOR_ACCEPTED_ONLY",
          "revision_digest": "81bc700ff37dd35347943a2e7a61f6ddf3c2dad9162ef1dc9fe437be6f9f7ad3",
          "schema_revision_ref": "BDB_SCHEMA_REGISTRY::attempt/1"
        }
      },
      {
        "campaign_id": "campaign_31fc162f11d95f1e",
        "stage_id": "E1",
        "lane_slot": "E1-C",
        "lane_title": "State, Persistence & Recovery",
        "strategy": "STATE_MUTATION_TRACE",
        "input_history_cut": {
          "accepted_head_hash": "5f38b2615dc2a4868f042349be8085a45e25163c75fd88b0e5dafb2e214937a3",
          "accepted_head_seq": 7,
          "campaign_id": "campaign_31fc162f11d95f1e",
          "governing_policy_ref": "pin:initial_governing_policy_ref",
          "governing_spec_refs": [
            "pin:initial_transition_profile_ref"
          ],
          "variant": "ACCEPTED_HISTORY_CUT"
        },
        "package_digest": "3cfe75184b3bacc0ccbbc2c056c2af0ca022dac76cb4d36f534972a5b214963f",
        "package_zip_path": "C:\\Projekty\\Audyty\\BDB Audit\\.product-smoke\\6937465a7a7543d6aa2286ac675d9902\\work\\artifacts\\campaign_31fc162f11d95f1e\\E1\\E1-C_State_Persistence_AND_Recovery_3cfe75184b3b_PACKAGE.zip",
        "package_zip_sha256": "cf31a47f1e0d532e98efdbbaa098ceba8e605776c3d67ead10287e1dff860db5",
        "prompt_sha256": "d6648c51d157881a189e787bed824aff537028a074b2568b07269aa5c041e377",
        "assignment_ref": {
          "digest_profile": "BDB-OBJECT-DIGEST-1",
          "kind": "assignment_manifest",
          "ref_class": "PRIOR_ACCEPTED_ONLY",
          "revision_digest": "7b2522f010462c655ea1f00bda0b798c9753653a349db2a10437a19a84a66e80",
          "schema_revision_ref": "BDB_SCHEMA_REGISTRY::assignment_manifest/1"
        },
        "attempt_ref": {
          "digest_profile": "BDB-OBJECT-DIGEST-1",
          "kind": "attempt",
          "ref_class": "PRIOR_ACCEPTED_ONLY",
          "revision_digest": "de879b80d8ee14bbd087a0f3890e36b7c21c45d307fcba7cf80f08477c974c83",
          "schema_revision_ref": "BDB_SCHEMA_REGISTRY::attempt/1"
        }
      },
      {
        "campaign_id": "campaign_31fc162f11d95f1e",
        "stage_id": "E1",
        "lane_slot": "E1-D",
        "lane_title": "Data, Catalog & Parsing",
        "strategy": "INPUT_PARSER_DIFFERENTIAL",
        "input_history_cut": {
          "accepted_head_hash": "5f38b2615dc2a4868f042349be8085a45e25163c75fd88b0e5dafb2e214937a3",
          "accepted_head_seq": 7,
          "campaign_id": "campaign_31fc162f11d95f1e",
          "governing_policy_ref": "pin:initial_governing_policy_ref",
          "governing_spec_refs": [
            "pin:initial_transition_profile_ref"
          ],
          "variant": "ACCEPTED_HISTORY_CUT"
        },
        "package_digest": "5c413b126abe38845190b8b5deb0ec485e9579a6b8b958cea91548eb787ef494",
        "package_zip_path": "C:\\Projekty\\Audyty\\BDB Audit\\.product-smoke\\6937465a7a7543d6aa2286ac675d9902\\work\\artifacts\\campaign_31fc162f11d95f1e\\E1\\E1-D_Data_Catalog_AND_Parsing_5c413b126abe_PACKAGE.zip",
        "package_zip_sha256": "bbbb452c8c3b6f5bb5dcd27321ef3b71a9c58296cb1616da7abe92e9405e8bbe",
        "prompt_sha256": "ebccb21d61f5b8381d81ef453f041eddfc37ababa7d3f8921b301f9d33432fbd",
        "assignment_ref": {
          "digest_profile": "BDB-OBJECT-DIGEST-1",
          "kind": "assignment_manifest",
          "ref_class": "PRIOR_ACCEPTED_ONLY",
          "revision_digest": "fd407c6b5952f895fd13df99060bba182aa6cff75d4f2853ab03a2f66045b024",
          "schema_revision_ref": "BDB_SCHEMA_REGISTRY::assignment_manifest/1"
        },
        "attempt_ref": {
          "digest_profile": "BDB-OBJECT-DIGEST-1",
          "kind": "attempt",
          "ref_class": "PRIOR_ACCEPTED_ONLY",
          "revision_digest": "7107669cb1774d92ae5a5d2712f7bc5c1c9da64e67acd4018620c747196386c4",
          "schema_revision_ref": "BDB_SCHEMA_REGISTRY::attempt/1"
        }
      },
      {
        "campaign_id": "campaign_31fc162f11d95f1e",
        "stage_id": "E1",
        "lane_slot": "E1-E",
        "lane_title": "Concurrency, Resources & Oracles",
        "strategy": "INTERACTION_CONCURRENCY_ANALYSIS",
        "input_history_cut": {
          "accepted_head_hash": "5f38b2615dc2a4868f042349be8085a45e25163c75fd88b0e5dafb2e214937a3",
          "accepted_head_seq": 7,
          "campaign_id": "campaign_31fc162f11d95f1e",
          "governing_policy_ref": "pin:initial_governing_policy_ref",
          "governing_spec_refs": [
            "pin:initial_transition_profile_ref"
          ],
          "variant": "ACCEPTED_HISTORY_CUT"
        },
        "package_digest": "2264c536b5002e4e53ca78a5d249a396f88eac93280c3730e26eca21e0b12d3e",
        "package_zip_path": "C:\\Projekty\\Audyty\\BDB Audit\\.product-smoke\\6937465a7a7543d6aa2286ac675d9902\\work\\artifacts\\campaign_31fc162f11d95f1e\\E1\\E1-E_Concurrency_Resources_AND_Oracles_2264c536b500_PACKAGE.zip",
        "package_zip_sha256": "29011c1e1d0c730d8305361327942120c02d1ad3c16d9112b4f907db30a3317c",
        "prompt_sha256": "63f948371e9ee0ad70c3f2ec83c61edbef19584056f0dc84b25bdfb60f00b2d6",
        "assignment_ref": {
          "digest_profile": "BDB-OBJECT-DIGEST-1",
          "kind": "assignment_manifest",
          "ref_class": "PRIOR_ACCEPTED_ONLY",
          "revision_digest": "4435b7b26ba4b833e21ab695f7e5fa6fc81a85eeac3d996f4b7e8c8c52771bc1",
          "schema_revision_ref": "BDB_SCHEMA_REGISTRY::assignment_manifest/1"
        },
        "attempt_ref": {
          "digest_profile": "BDB-OBJECT-DIGEST-1",
          "kind": "attempt",
          "ref_class": "PRIOR_ACCEPTED_ONLY",
          "revision_digest": "5abac200fda1de1ab880529e94fc19fdcd3a518667d04b12776df3a707ed2067",
          "schema_revision_ref": "BDB_SCHEMA_REGISTRY::attempt/1"
        }
      }
    ],
    "action": "product.status"
  },
  "local_runs": [
    {
      "path": "C:\\Projekty\\Audyty\\BDB Audit\\.product-smoke\\6937465a7a7543d6aa2286ac675d9902\\checks-pass",
      "verification": {
        "status": "PASS",
        "run_id": "sum-control",
        "spec_digest": "d20575215d375f2bc73c2aa31861ca0ef78de06b3e2d43fa6e075d5ee248fde9",
        "receipt_digest": "a82bb2e7552683398607d3cdb2a1d56a245e7c44319de7d108baa4be242cc927",
        "supervisor_status": "SUCCESS",
        "cleanup_status": "CLEAN",
        "stdout_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "stderr_sha256": "1a52ff93b2b7c8bc576900f70c9062f5baedb573cf55507ec33070c999cd9b12"
      },
      "authority": "LOCAL_RECEIPT_INTEGRITY_ONLY; NOT_ACCEPTED_AUDITOR_RESULT"
    },
    {
      "path": "C:\\Projekty\\Audyty\\BDB Audit\\.product-smoke\\6937465a7a7543d6aa2286ac675d9902\\checks-detected-defect",
      "verification": {
        "status": "PASS",
        "run_id": "clamp-defect",
        "spec_digest": "5758d964974912aca2709074453e86c443cd993bebf68fef42e76968fde7cc9f",
        "receipt_digest": "1fb1d7f0d7518b811586dbfe82622e72fcd1024071861dd4ef606590f584d50d",
        "supervisor_status": "TARGET_NONZERO",
        "cleanup_status": "CLEAN",
        "stdout_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "stderr_sha256": "d851c7048df1d3f1847236b9566fc3f43e0846b8cf9c6e5b9dca8eadddef59f5"
      },
      "authority": "LOCAL_RECEIPT_INTEGRITY_ONLY; NOT_ACCEPTED_AUDITOR_RESULT"
    }
  ],
  "untrusted_result_inspections": []
}
```

# BDB Audit Report

Campaign: `campaign_31fc162f11d95f1e`  
Scope: **PARTIAL**  
Report model SHA-256: `af2aa19d5eec248ee4e0c644b6b050602eb89a13ec2b1564d3364ad6b1ff88c6`  
Accepted head: `0db694fea7bffc88a899d7fd031bd792c1b61d6034e3128f57c5617572835cab`  
Source identity: `{"authority_mode": "AUTHORIZED_GIT", "completeness_state": "COMPLETE_SOURCE", "git_commit_object_id": "f27387755f3a88af400dd930280721eebd5506fd", "git_tree_object_id": "f27387755f3a88af400dd930280721eebd5506fd", "repository_authority_ref": {"digest_profile": "BDB-OBJECT-DIGEST-1", "kind": "repository_or_snapshot_authority_ref", "ref_class": "SOURCE_AUTHORITY_REF", "revision_digest": "5f5528f162bf2246598c7e9f7b9ef26d544dd90252a36666301488a285d83169", "schema_revision_ref": "BDB_TARGET/repository_or_snapshot_authority_ref"}, "source_generation_id": "source_gen_campaign_31fc162f11d95f1e", "source_generation_ref": {"digest_profile": "BDB-OBJECT-DIGEST-1", "kind": "source_generation", "ref_class": "CONTENT_OR_PRIOR", "revision_digest": "b457d8292aab4da2c544346eb8af1f9231fcfaf4b534cf1d617d3e37fe1d98ae", "schema_revision_ref": "BDB_SCHEMA_REGISTRY::source_generation/1"}, "source_identity_ref": {"digest_profile": "BDB-OBJECT-DIGEST-1", "kind": "source_identity", "ref_class": "CONTENT_OR_PRIOR", "revision_digest": "6bdf0d37effcb3b0aaaa1748e3de1ada9a0d33b4ff4297d5fcc5b3e4f57e9b9f", "schema_revision_ref": "BDB_SCHEMA_REGISTRY::source_identity/1"}}`

All entries below are explicitly classified as accepted FACT, derived INTERPRETATION, PROPOSAL, or UNKNOWN.

## Accepted facts

### campaign_genesis — 1da9310e433084943750637ea2a94e871f7a1038c863dd29d3ffba1371eae473

Classification: **FACT**  
Accepted seq: `1`

```json
{
  "application_generation_ref": {
    "digest_profile": "BDB-OBJECT-DIGEST-1",
    "kind": "application_generation_ref",
    "ref_class": "CONTENT_OR_PRIOR",
    "revision_digest": "585cb81b525f0247625351d572f2ec063819e4349a616e00f68a2c8b4753f75e",
    "schema_revision_ref": "BDB_TARGET/application_generation_ref"
  },
  "bootstrap_admission_decision_ref": {
    "digest_profile": "BDB-OBJECT-DIGEST-1",
    "kind": "bootstrap_admission_decision",
    "ref_class": "CONTENT_OR_PRIOR",
    "revision_digest": "34febc7dc47d9371039147a4c98317698805495146701923b088dcefbfa79f9c",
    "schema_revision_ref": "BDB_SCHEMA_REGISTRY::bootstrap_admission_decision/1"
  },
  "campaign_id": "campaign_31fc162f11d95f1e",
  "input_history_cut": {
    "governing_policy_ref": "pin:initial_governing_policy_ref",
    "governing_spec_refs": [
      "pin:initial_transition_profile_ref"
    ],
    "history_namespace_ref": "pin:allowed_history_namespace_ref",
    "variant": "EMPTY_HISTORY_CUT"
  },
  "legacy_origin_refs": [
    {
      "digest_profile": "BDB-OBJECT-DIGEST-1",
      "kind": "legacy_raw_ref",
      "ref_class": "CONTENT_OR_PRIOR",
      "revision_digest": "6c782187e776b2ea8c0a8411a33fa95aff32482199b909ce62cde99a50583216",
      "schema_revision_ref": "BDB_SCHEMA_REGISTRY::legacy_raw_ref/1"
    }
  ],
  "owner_operator_authority_ref": {
    "digest_profile": "BDB-OBJECT-DIGEST-1",
    "kind": "owner_operator_authority_ref",
    "ref_class": "PINNED_INSTALLATION_REF",
    "revision_digest": "9bf5e5adb755633c31c2432ab6b69438562fb2e98cf94a3b0e7e0b1a97a767af",
    "schema_revision_ref": "BDB_TARGET/owner_operator_authority_ref"
  },
  "protocol_policy_bundle_ref": {
    "digest_profile": "BDB-OBJECT-DIGEST-1",
    "kind": "protocol_policy_bundle_ref",
    "ref_class": "CONTENT_OR_PRIOR",
    "revision_digest": "f49a29e94fd58012fc3a826da68ec5bec641430512eb9fc9ab46a7d80fae2a16",
    "schema_revision_ref": "BDB_TARGET/protocol_policy_bundle_ref"
  },
  "schema_set_ref": {
    "digest_profile": "BDB-OBJECT-DIGEST-1",
    "kind": "schema_set_ref",
    "ref_class": "CONTENT_OR_PRIOR",
    "revision_digest": "41f51ea63e5a5095ae2df817782f37491e0b783c1763ddbe66ac5b71c3da264e",
    "schema_revision_ref": "BDB_TARGET/schema_set_ref"
  },
  "source_generation_ref": {
    "digest_profile": "BDB-OBJECT-DIGEST-1",
    "kind": "source_generation",
    "ref_class": "CONTENT_OR_PRIOR",
    "revision_digest": "b457d8292aab4da2c544346eb8af1f9231fcfaf4b534cf1d617d3e37fe1d98ae",
    "schema_revision_ref": "BDB_SCHEMA_REGISTRY::source_generation/1"
  },
  "trust_profile_ref": {
    "digest_profile": "BDB-OBJECT-DIGEST-1",
    "kind": "trust_profile",
    "ref_class": "PINNED_INSTALLATION_REF",
    "revision_digest": "92d99e5aa0b98af7d5326a22be20fff7a69c1b188de35e8a2b1ae66366593077",
    "schema_revision_ref": "BDB_TARGET/trust_profile"
  }
}
```

### source_generation — b457d8292aab4da2c544346eb8af1f9231fcfaf4b534cf1d617d3e37fe1d98ae

Classification: **FACT**  
Accepted seq: `1`

```json
{
  "materialized_source_manifest_ref": {
    "digest_profile": "BDB-OBJECT-DIGEST-1",
    "kind": "source_manifest",
    "ref_class": "CONTENT_OR_PRIOR",
    "revision_digest": "dad418b73f4466ca4146c2c91deff8a56a0befd7e01b867c6dce5a47f7674e7d",
    "schema_revision_ref": "BDB_SCHEMA_REGISTRY::source_manifest/1"
  },
  "repository_authority_ref": {
    "digest_profile": "BDB-OBJECT-DIGEST-1",
    "kind": "repository_or_snapshot_authority_ref",
    "ref_class": "SOURCE_AUTHORITY_REF",
    "revision_digest": "5f5528f162bf2246598c7e9f7b9ef26d544dd90252a36666301488a285d83169",
    "schema_revision_ref": "BDB_TARGET/repository_or_snapshot_authority_ref"
  },
  "representation_refs": [],
  "source_generation_id": "source_gen_campaign_31fc162f11d95f1e",
  "source_identity_profile_ref": {
    "digest_profile": "BDB-OBJECT-DIGEST-1",
    "kind": "source_identity_profile_pin",
    "ref_class": "PINNED_PROFILE_REF",
    "revision_digest": "60b43bd150fb84c81bfa632284dd144dd293f6fe1b08a0214cd6927101e276a1",
    "schema_revision_ref": "BDB_TARGET/source_identity_profile_pin"
  },
  "source_identity_ref": {
    "digest_profile": "BDB-OBJECT-DIGEST-1",
    "kind": "source_identity",
    "ref_class": "CONTENT_OR_PRIOR",
    "revision_digest": "6bdf0d37effcb3b0aaaa1748e3de1ada9a0d33b4ff4297d5fcc5b3e4f57e9b9f",
    "schema_revision_ref": "BDB_SCHEMA_REGISTRY::source_identity/1"
  }
}
```

### source_identity — 6bdf0d37effcb3b0aaaa1748e3de1ada9a0d33b4ff4297d5fcc5b3e4f57e9b9f

Classification: **FACT**  
Accepted seq: `1`

```json
{
  "authority_mode": "AUTHORIZED_GIT",
  "authorized_repository_or_snapshot_ref": {
    "digest_profile": "BDB-OBJECT-DIGEST-1",
    "kind": "repository_or_snapshot_authority_ref",
    "ref_class": "SOURCE_AUTHORITY_REF",
    "revision_digest": "5f5528f162bf2246598c7e9f7b9ef26d544dd90252a36666301488a285d83169",
    "schema_revision_ref": "BDB_TARGET/repository_or_snapshot_authority_ref"
  },
  "completeness_state": "COMPLETE_SOURCE",
  "git_commit_object_id": "f27387755f3a88af400dd930280721eebd5506fd",
  "git_tree_object_id": "f27387755f3a88af400dd930280721eebd5506fd",
  "materialized_source_manifest_ref": {
    "digest_profile": "BDB-OBJECT-DIGEST-1",
    "kind": "source_manifest",
    "ref_class": "CONTENT_OR_PRIOR",
    "revision_digest": "dad418b73f4466ca4146c2c91deff8a56a0befd7e01b867c6dce5a47f7674e7d",
    "schema_revision_ref": "BDB_SCHEMA_REGISTRY::source_manifest/1"
  },
  "profile_ref": {
    "digest_profile": "BDB-OBJECT-DIGEST-1",
    "kind": "source_identity_profile_pin",
    "ref_class": "PINNED_PROFILE_REF",
    "revision_digest": "60b43bd150fb84c81bfa632284dd144dd293f6fe1b08a0214cd6927101e276a1",
    "schema_revision_ref": "BDB_TARGET/source_identity_profile_pin"
  }
}
```

## Interpretations

NOT_ASSESSED

## Proposals

NOT_ASSESSED

## Unknowns / blockers

NOT_ASSESSED
