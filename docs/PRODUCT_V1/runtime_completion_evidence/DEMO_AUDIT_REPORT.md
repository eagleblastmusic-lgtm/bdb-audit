# BDB Audit PRODUCT-V1 — raport częściowy

Audyt E1-E6: **NOT_COMPLETED**. NF02: **OPEN**. Import wyników: **BLOCKED**.

NF02 OPEN: brak niezależnie autoryzowanego producenta i kwalifikowanej aktywacji. Zachowaj ZIP poza historią. Przygotowanie paczek, lokalne kontrole i raport częściowy są dostępne; E1-E6 nie jest ukończone.

Lokalne komendy dowodzą wyłącznie wykonania wskazanych kontroli. Integralność receipt nie ustanawia autoryzacji producenta ani związania z kampanią. Nie są kwalifikacją ani wynikiem zewnętrznego audytora.

Kontrole ZIP poniżej mają status INSPECTED_UNTRUSTED. Ich ustalenia są nieprzyjętymi deklaracjami; zgodność bajtów i kontekstu nie dowodzi autorstwa ani prawdziwości.

```json
{
  "campaign": {
    "status": "READY_FOR_REVIEW",
    "store_path": "C:\\Projekty\\Audyty\\BDB Audit\\.product-smoke\\6311eaab595d4e77b8f9ec046e0d69e4\\work\\campaign.sqlite",
    "campaign_id": "campaign_391968c1b4ec2b2d",
    "accepted_history_cut": {
      "variant": "ACCEPTED_HISTORY_CUT",
      "governing_policy_ref": "pin:initial_governing_policy_ref",
      "governing_spec_refs": [
        "pin:initial_transition_profile_ref"
      ],
      "campaign_id": "campaign_391968c1b4ec2b2d",
      "accepted_head_seq": 8,
      "accepted_head_hash": "ca992a38ff4065fca76418c3e901ac47fb6d00aab35ed2073a95cce58f9acef1"
    },
    "workflow": {
      "status": "SUCCESS",
      "campaign_id": "campaign_391968c1b4ec2b2d",
      "store_path": "C:\\Projekty\\Audyty\\BDB Audit\\.product-smoke\\6311eaab595d4e77b8f9ec046e0d69e4\\work\\campaign.sqlite",
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
      "source_commit_sha": "62c7917182cea946c11f388a21bc0c8f7418ebee",
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
        "campaign_id": "campaign_391968c1b4ec2b2d",
        "stage_id": "E1",
        "lane_slot": "E1-A",
        "lane_title": "General Systems & Architecture",
        "strategy": "STRUCTURAL_ENUMERATION",
        "input_history_cut": {
          "accepted_head_hash": "96f3e70b223cea912743f215f340d0a3df73edd4fe27b45f5b6f6727380c7d6f",
          "accepted_head_seq": 7,
          "campaign_id": "campaign_391968c1b4ec2b2d",
          "governing_policy_ref": "pin:initial_governing_policy_ref",
          "governing_spec_refs": [
            "pin:initial_transition_profile_ref"
          ],
          "variant": "ACCEPTED_HISTORY_CUT"
        },
        "package_digest": "3ff8a02657670a4cc7c7a59fee76f7c7ed34e0c818288e0980e79689f062cb73",
        "package_zip_path": "C:\\Projekty\\Audyty\\BDB Audit\\.product-smoke\\6311eaab595d4e77b8f9ec046e0d69e4\\work\\artifacts\\campaign_391968c1b4ec2b2d\\E1\\E1-A_General_Systems_AND_Architecture_3ff8a0265767_PACKAGE.zip",
        "package_zip_sha256": "c009321a272c286f7fbc7466d9956fdffc1bab936f2c958b8c24a18053b2ddae",
        "prompt_sha256": "35ec33b323c8007cbfca017fb251e5162a521c1c34581c6e0c92420ec4080b3d",
        "assignment_ref": {
          "digest_profile": "BDB-OBJECT-DIGEST-1",
          "kind": "assignment_manifest",
          "ref_class": "PRIOR_ACCEPTED_ONLY",
          "revision_digest": "d3e37a3d2d5c792cf56df662a04c89604af360ee4c8cc20bd9f686bedd13f46f",
          "schema_revision_ref": "BDB_SCHEMA_REGISTRY::assignment_manifest/1"
        },
        "attempt_ref": {
          "digest_profile": "BDB-OBJECT-DIGEST-1",
          "kind": "attempt",
          "ref_class": "PRIOR_ACCEPTED_ONLY",
          "revision_digest": "f263b4e177d747424344a07fce9276be4bb47b095258e6ab6d443cdf1c6f9d6d",
          "schema_revision_ref": "BDB_SCHEMA_REGISTRY::attempt/1"
        }
      },
      {
        "campaign_id": "campaign_391968c1b4ec2b2d",
        "stage_id": "E1",
        "lane_slot": "E1-B",
        "lane_title": "Security, Trust & Authority",
        "strategy": "AUTHORITY_BOUNDARY_ANALYSIS",
        "input_history_cut": {
          "accepted_head_hash": "96f3e70b223cea912743f215f340d0a3df73edd4fe27b45f5b6f6727380c7d6f",
          "accepted_head_seq": 7,
          "campaign_id": "campaign_391968c1b4ec2b2d",
          "governing_policy_ref": "pin:initial_governing_policy_ref",
          "governing_spec_refs": [
            "pin:initial_transition_profile_ref"
          ],
          "variant": "ACCEPTED_HISTORY_CUT"
        },
        "package_digest": "2505a0ae3d3c941625af05d631da7ffd0d63184eebde45aa8e8fae36d594c41b",
        "package_zip_path": "C:\\Projekty\\Audyty\\BDB Audit\\.product-smoke\\6311eaab595d4e77b8f9ec046e0d69e4\\work\\artifacts\\campaign_391968c1b4ec2b2d\\E1\\E1-B_Security_Trust_AND_Authority_2505a0ae3d3c_PACKAGE.zip",
        "package_zip_sha256": "61b517d803bed6030af71fbfe07eb3cfc309341924523459b6cba8c2e6c631d4",
        "prompt_sha256": "8c8588b77cc46c7d747e393ce60e28108bcf73f7ede22d87df4a46d348fdb06a",
        "assignment_ref": {
          "digest_profile": "BDB-OBJECT-DIGEST-1",
          "kind": "assignment_manifest",
          "ref_class": "PRIOR_ACCEPTED_ONLY",
          "revision_digest": "d6be33ea20f8f4e9eea5fd92fc3cbb410d2aa66c6331e860783d4de4d2ded47c",
          "schema_revision_ref": "BDB_SCHEMA_REGISTRY::assignment_manifest/1"
        },
        "attempt_ref": {
          "digest_profile": "BDB-OBJECT-DIGEST-1",
          "kind": "attempt",
          "ref_class": "PRIOR_ACCEPTED_ONLY",
          "revision_digest": "73210aa9e29a30649b0fe38516ac23a7c9732148a7e6e9c718639e52db80e50d",
          "schema_revision_ref": "BDB_SCHEMA_REGISTRY::attempt/1"
        }
      },
      {
        "campaign_id": "campaign_391968c1b4ec2b2d",
        "stage_id": "E1",
        "lane_slot": "E1-C",
        "lane_title": "State, Persistence & Recovery",
        "strategy": "STATE_MUTATION_TRACE",
        "input_history_cut": {
          "accepted_head_hash": "96f3e70b223cea912743f215f340d0a3df73edd4fe27b45f5b6f6727380c7d6f",
          "accepted_head_seq": 7,
          "campaign_id": "campaign_391968c1b4ec2b2d",
          "governing_policy_ref": "pin:initial_governing_policy_ref",
          "governing_spec_refs": [
            "pin:initial_transition_profile_ref"
          ],
          "variant": "ACCEPTED_HISTORY_CUT"
        },
        "package_digest": "a71212c3b545e3cc3e9a395fa101ad11e41647a32f5ac78efa39ce0facdd8b4f",
        "package_zip_path": "C:\\Projekty\\Audyty\\BDB Audit\\.product-smoke\\6311eaab595d4e77b8f9ec046e0d69e4\\work\\artifacts\\campaign_391968c1b4ec2b2d\\E1\\E1-C_State_Persistence_AND_Recovery_a71212c3b545_PACKAGE.zip",
        "package_zip_sha256": "95e96e32ebf3771f4431990a4a1bc096adafc89446749cce18f521e1611b5760",
        "prompt_sha256": "5255b192a77a2b5c92b7fac12467158e4c941b2b0b2e555702c8e1a399878903",
        "assignment_ref": {
          "digest_profile": "BDB-OBJECT-DIGEST-1",
          "kind": "assignment_manifest",
          "ref_class": "PRIOR_ACCEPTED_ONLY",
          "revision_digest": "a1066f9b7a13f464d49d8cdca0cd32adc06bbee57020f9592914e25c4488b84c",
          "schema_revision_ref": "BDB_SCHEMA_REGISTRY::assignment_manifest/1"
        },
        "attempt_ref": {
          "digest_profile": "BDB-OBJECT-DIGEST-1",
          "kind": "attempt",
          "ref_class": "PRIOR_ACCEPTED_ONLY",
          "revision_digest": "4c4a90fe3b438177d83aa1277cebfad33aa77e63b9ff8b1b8bf649f506d8f84d",
          "schema_revision_ref": "BDB_SCHEMA_REGISTRY::attempt/1"
        }
      },
      {
        "campaign_id": "campaign_391968c1b4ec2b2d",
        "stage_id": "E1",
        "lane_slot": "E1-D",
        "lane_title": "Data, Catalog & Parsing",
        "strategy": "INPUT_PARSER_DIFFERENTIAL",
        "input_history_cut": {
          "accepted_head_hash": "96f3e70b223cea912743f215f340d0a3df73edd4fe27b45f5b6f6727380c7d6f",
          "accepted_head_seq": 7,
          "campaign_id": "campaign_391968c1b4ec2b2d",
          "governing_policy_ref": "pin:initial_governing_policy_ref",
          "governing_spec_refs": [
            "pin:initial_transition_profile_ref"
          ],
          "variant": "ACCEPTED_HISTORY_CUT"
        },
        "package_digest": "b63d39b06d5d0e7a069727b452d56d98c3ea050ddb49a7d3f3f5dd343297c378",
        "package_zip_path": "C:\\Projekty\\Audyty\\BDB Audit\\.product-smoke\\6311eaab595d4e77b8f9ec046e0d69e4\\work\\artifacts\\campaign_391968c1b4ec2b2d\\E1\\E1-D_Data_Catalog_AND_Parsing_b63d39b06d5d_PACKAGE.zip",
        "package_zip_sha256": "214bdab5c4dae3c2fb1bbbb84d505cee6e750f3dc97b7be12414e42b0c291261",
        "prompt_sha256": "e29a10986d0ed6a2005127417a1e8cedc1faca03f5a1f17fd8f52a7824945631",
        "assignment_ref": {
          "digest_profile": "BDB-OBJECT-DIGEST-1",
          "kind": "assignment_manifest",
          "ref_class": "PRIOR_ACCEPTED_ONLY",
          "revision_digest": "a34c10f819962b19fa9dd11fab6f78a6920efef1063cbe00b49287b6874bdbb3",
          "schema_revision_ref": "BDB_SCHEMA_REGISTRY::assignment_manifest/1"
        },
        "attempt_ref": {
          "digest_profile": "BDB-OBJECT-DIGEST-1",
          "kind": "attempt",
          "ref_class": "PRIOR_ACCEPTED_ONLY",
          "revision_digest": "5b301769c9992261837edc5db75fcde9494dd0a0b781ab76e7031b2caf0b412e",
          "schema_revision_ref": "BDB_SCHEMA_REGISTRY::attempt/1"
        }
      },
      {
        "campaign_id": "campaign_391968c1b4ec2b2d",
        "stage_id": "E1",
        "lane_slot": "E1-E",
        "lane_title": "Concurrency, Resources & Oracles",
        "strategy": "INTERACTION_CONCURRENCY_ANALYSIS",
        "input_history_cut": {
          "accepted_head_hash": "96f3e70b223cea912743f215f340d0a3df73edd4fe27b45f5b6f6727380c7d6f",
          "accepted_head_seq": 7,
          "campaign_id": "campaign_391968c1b4ec2b2d",
          "governing_policy_ref": "pin:initial_governing_policy_ref",
          "governing_spec_refs": [
            "pin:initial_transition_profile_ref"
          ],
          "variant": "ACCEPTED_HISTORY_CUT"
        },
        "package_digest": "247b9a73ae157eabee411709e74ceb65391c602a1608d82fd514e0337c1a0a1d",
        "package_zip_path": "C:\\Projekty\\Audyty\\BDB Audit\\.product-smoke\\6311eaab595d4e77b8f9ec046e0d69e4\\work\\artifacts\\campaign_391968c1b4ec2b2d\\E1\\E1-E_Concurrency_Resources_AND_Oracles_247b9a73ae15_PACKAGE.zip",
        "package_zip_sha256": "72774545b6e442ade85c3ed476d4b36955c96f80ced0dd40ef37f5440adde52a",
        "prompt_sha256": "929f233b372ddc1173c2c71db86d96877c8d9ded7d0b20c4ed1a67031f0a16d1",
        "assignment_ref": {
          "digest_profile": "BDB-OBJECT-DIGEST-1",
          "kind": "assignment_manifest",
          "ref_class": "PRIOR_ACCEPTED_ONLY",
          "revision_digest": "4d072ad5279d092a2b09146694fc550e570cd531b168989ca49f398e0b6812ec",
          "schema_revision_ref": "BDB_SCHEMA_REGISTRY::assignment_manifest/1"
        },
        "attempt_ref": {
          "digest_profile": "BDB-OBJECT-DIGEST-1",
          "kind": "attempt",
          "ref_class": "PRIOR_ACCEPTED_ONLY",
          "revision_digest": "6e1e1866881dcb3f8ffa37b72c06b963f8bf75712d7752f4ed93a7bc57d50a2e",
          "schema_revision_ref": "BDB_SCHEMA_REGISTRY::attempt/1"
        }
      }
    ],
    "action": "product.status"
  },
  "local_runs": [
    {
      "path": "C:\\Projekty\\Audyty\\BDB Audit\\.product-smoke\\6311eaab595d4e77b8f9ec046e0d69e4\\checks-pass",
      "verification": {
        "status": "PASS",
        "run_id": "sum-control",
        "spec_digest": "8a76dc057a3d462f1196e44f6f49b4bb57d505a0a3199f65bc9230a1c55ad1e6",
        "receipt_digest": "ee365993dad6321399dc839b32f852cb6ea3ae2cc9c8f1e50cb734e8ff2c7de2",
        "supervisor_status": "SUCCESS",
        "cleanup_status": "CLEAN",
        "stdout_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "stderr_sha256": "1a52ff93b2b7c8bc576900f70c9062f5baedb573cf55507ec33070c999cd9b12"
      },
      "authority": "LOCAL_RECEIPT_INTEGRITY_ONLY; NOT_ACCEPTED_AUDITOR_RESULT"
    },
    {
      "path": "C:\\Projekty\\Audyty\\BDB Audit\\.product-smoke\\6311eaab595d4e77b8f9ec046e0d69e4\\checks-detected-defect",
      "verification": {
        "status": "PASS",
        "run_id": "clamp-defect",
        "spec_digest": "fbaadc59181c1cfb67466305bf4ca8a662a3f0ce76552c7fa415e09bcf2ecdf4",
        "receipt_digest": "7ad7e287f963f9478de8f9dc226825bd6881a2d17dac81039793b24bab9f1058",
        "supervisor_status": "TARGET_NONZERO",
        "cleanup_status": "CLEAN",
        "stdout_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "stderr_sha256": "b4c1e620517cfb28d08cdffd0dcc2e8bbf827e246702858c44489506ed29b170"
      },
      "authority": "LOCAL_RECEIPT_INTEGRITY_ONLY; NOT_ACCEPTED_AUDITOR_RESULT"
    }
  ],
  "untrusted_result_inspections": []
}
```

# BDB Audit Report

Campaign: `campaign_391968c1b4ec2b2d`  
Scope: **PARTIAL**  
Report model SHA-256: `d61ebb4f3e00937b9575c01417817ccaaf42564e493e3f25b6c3fb4fa86a66a9`  
Accepted head: `ca992a38ff4065fca76418c3e901ac47fb6d00aab35ed2073a95cce58f9acef1`  
Source identity: `{"authority_mode": "AUTHORIZED_GIT", "completeness_state": "COMPLETE_SOURCE", "git_commit_object_id": "62c7917182cea946c11f388a21bc0c8f7418ebee", "git_tree_object_id": "62c7917182cea946c11f388a21bc0c8f7418ebee", "repository_authority_ref": {"digest_profile": "BDB-OBJECT-DIGEST-1", "kind": "repository_or_snapshot_authority_ref", "ref_class": "SOURCE_AUTHORITY_REF", "revision_digest": "950f2911e4ccf380a72531cd0372cc035bc924ddd4e01b2d87631d2be8ddfeae", "schema_revision_ref": "BDB_TARGET/repository_or_snapshot_authority_ref"}, "source_generation_id": "source_gen_campaign_391968c1b4ec2b2d", "source_generation_ref": {"digest_profile": "BDB-OBJECT-DIGEST-1", "kind": "source_generation", "ref_class": "CONTENT_OR_PRIOR", "revision_digest": "bc60083d6d82ee9e7b7b79c875d7a000ae5d552c0f5c97e86671ad16f113a262", "schema_revision_ref": "BDB_SCHEMA_REGISTRY::source_generation/1"}, "source_identity_ref": {"digest_profile": "BDB-OBJECT-DIGEST-1", "kind": "source_identity", "ref_class": "CONTENT_OR_PRIOR", "revision_digest": "c777f003343b512c11c7bd5429bba696761864c768d6ce0038fc83c6dc552e4d", "schema_revision_ref": "BDB_SCHEMA_REGISTRY::source_identity/1"}}`

All entries below are explicitly classified as accepted FACT, derived INTERPRETATION, PROPOSAL, or UNKNOWN.

## Accepted facts

### campaign_genesis — b0fd393f2342fec98a50ea05116d66a6da7862a89513ec8870c69c27b05cd611

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
    "revision_digest": "1e78484f41fd33e713eb6b96aaaac8069f704ed979ec3485bd34a5869bd70302",
    "schema_revision_ref": "BDB_SCHEMA_REGISTRY::bootstrap_admission_decision/1"
  },
  "campaign_id": "campaign_391968c1b4ec2b2d",
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
      "revision_digest": "ff9009006707f888906f2b65abc53dfeaecead5af914e30b372937bb21fb1ae0",
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
    "revision_digest": "bc60083d6d82ee9e7b7b79c875d7a000ae5d552c0f5c97e86671ad16f113a262",
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

### source_generation — bc60083d6d82ee9e7b7b79c875d7a000ae5d552c0f5c97e86671ad16f113a262

Classification: **FACT**  
Accepted seq: `1`

```json
{
  "materialized_source_manifest_ref": {
    "digest_profile": "BDB-OBJECT-DIGEST-1",
    "kind": "source_manifest",
    "ref_class": "CONTENT_OR_PRIOR",
    "revision_digest": "add1e87f15bb9a4aaa6373ef1d69e81a7fe910e10c7e85948dcde7e508e77d62",
    "schema_revision_ref": "BDB_SCHEMA_REGISTRY::source_manifest/1"
  },
  "repository_authority_ref": {
    "digest_profile": "BDB-OBJECT-DIGEST-1",
    "kind": "repository_or_snapshot_authority_ref",
    "ref_class": "SOURCE_AUTHORITY_REF",
    "revision_digest": "950f2911e4ccf380a72531cd0372cc035bc924ddd4e01b2d87631d2be8ddfeae",
    "schema_revision_ref": "BDB_TARGET/repository_or_snapshot_authority_ref"
  },
  "representation_refs": [],
  "source_generation_id": "source_gen_campaign_391968c1b4ec2b2d",
  "source_identity_profile_ref": {
    "digest_profile": "BDB-OBJECT-DIGEST-1",
    "kind": "source_identity_profile_pin",
    "ref_class": "PINNED_PROFILE_REF",
    "revision_digest": "dbb3fe77b858ccc0c3e551d51c7769710e14438a169ce443e201b7c0dfe26e67",
    "schema_revision_ref": "BDB_TARGET/source_identity_profile_pin"
  },
  "source_identity_ref": {
    "digest_profile": "BDB-OBJECT-DIGEST-1",
    "kind": "source_identity",
    "ref_class": "CONTENT_OR_PRIOR",
    "revision_digest": "c777f003343b512c11c7bd5429bba696761864c768d6ce0038fc83c6dc552e4d",
    "schema_revision_ref": "BDB_SCHEMA_REGISTRY::source_identity/1"
  }
}
```

### source_identity — c777f003343b512c11c7bd5429bba696761864c768d6ce0038fc83c6dc552e4d

Classification: **FACT**  
Accepted seq: `1`

```json
{
  "authority_mode": "AUTHORIZED_GIT",
  "authorized_repository_or_snapshot_ref": {
    "digest_profile": "BDB-OBJECT-DIGEST-1",
    "kind": "repository_or_snapshot_authority_ref",
    "ref_class": "SOURCE_AUTHORITY_REF",
    "revision_digest": "950f2911e4ccf380a72531cd0372cc035bc924ddd4e01b2d87631d2be8ddfeae",
    "schema_revision_ref": "BDB_TARGET/repository_or_snapshot_authority_ref"
  },
  "completeness_state": "COMPLETE_SOURCE",
  "git_commit_object_id": "62c7917182cea946c11f388a21bc0c8f7418ebee",
  "git_tree_object_id": "62c7917182cea946c11f388a21bc0c8f7418ebee",
  "materialized_source_manifest_ref": {
    "digest_profile": "BDB-OBJECT-DIGEST-1",
    "kind": "source_manifest",
    "ref_class": "CONTENT_OR_PRIOR",
    "revision_digest": "add1e87f15bb9a4aaa6373ef1d69e81a7fe910e10c7e85948dcde7e508e77d62",
    "schema_revision_ref": "BDB_SCHEMA_REGISTRY::source_manifest/1"
  },
  "profile_ref": {
    "digest_profile": "BDB-OBJECT-DIGEST-1",
    "kind": "source_identity_profile_pin",
    "ref_class": "PINNED_PROFILE_REF",
    "revision_digest": "dbb3fe77b858ccc0c3e551d51c7769710e14438a169ce443e201b7c0dfe26e67",
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
