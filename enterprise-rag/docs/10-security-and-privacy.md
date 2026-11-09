# 10. Security and Privacy Design

## 1. Security principles
The platform must treat all user input and uploaded content as untrusted. Authorization is enforced before retrieval or LLM invocation. Security design includes identity, access control, prompt defense, document safety, and operational governance.

## 2. Authentication
- Use secure password hashing with a modern algorithm such as bcrypt or Argon2.
- Support MFA for privileged roles.
- Use short-lived access tokens and refresh policies.
- Bind tokens to tenant context and user identity.

## 3. Authorization model
- Role-based access control is enforced from backend services.
- Department membership and document ACLs are resolved centrally.
- Client-supplied organization IDs are never treated as authorization evidence.
- Default deny model applies to all access.

## 4. Tenant isolation
Tenant isolation must be enforced at the application layer and recommended in PostgreSQL with RLS. Every query must resolve and validate the user’s organization before retrieving any documents or conversations.

## 5. Document access control
Document access must verify:
- user belongs to the correct tenant,
- document is active and not deleted,
- department authorization or explicit allow exists,
- explicit deny rules are not overridden,
- no cross-tenant or cross-department access occurs via client input.

## 6. API security
- TLS for all external requests.
- Input validation with Pydantic models.
- CSRF protection for browser sessions if cookies are used.
- Rate limiting per tenant, user, and route.
- Structured request IDs for correlation and audit logs.

## 7. File upload security
- Validate file type and file size.
- Scan uploaded documents for malware and suspicious content.
- Store files in object storage with restricted access and tenant-specific paths.
- Reject or quarantine suspicious files before processing.

## 8. Prompt injection protection
Prompt injection must be treated as a security issue for both user prompts and retrieved documents. Countermeasures include:
- retrieval-isolated evidence blocks,
- explicit instruction separation,
- refusal on unsupported or untrusted content,
- citation verification to reduce unsupported generation,
- no automatic trust in retrieved content.

## 9. Indirect prompt injection through documents
Documents may attempt to manipulate the LLM by including commands or instructions. To mitigate this:
- retrieved text is not allowed to alter policy decisions directly,
- the model receives a system policy that never allows document content to override authorization,
- the platform treats all retrieved content as evidence, not instructions.

## 10. Privacy considerations
- Employee and organizational data must be segregated.
- Sensitive documents may require encryption at rest and key rotation.
- Data retention should be configurable by tenant and compliance requirement.
- Secure deletion must remove traces from storage and vector indexes under controlled policy.

## 11. Audit logging
Audit logs must record:
- request ID,
- user identity,
- organization and tenant context,
- action type,
- target entity,
- timestamps,
- result (allow/deny/failure),
- IP and metadata as permitted.

## 12. Threat matrix
| Threat | Attack scenario | Impact | Likelihood | Mitigation | Verification |
|---|---|---|---|---|---|
| Cross-tenant data leak | User manipulates org ID in request | Critical | Medium | Backend validation + RLS + Qdrant filters | Cross-tenant tests |
| Prompt injection | Document contains malicious instructions | High | High | Evidence isolation and strict generation contract | Security eval suite |
| Unauthorized document access | User shares a document URL with different tenant | High | Medium | ACL evaluation + policy checks | penetration tests |
| Malware upload | Malicious PDF is uploaded | High | Medium | malware scan + quarantine + object isolation | upload test cases |
| Data retention drift | Deleted docs remain in object storage | Medium | Medium | retention policy and secure deletion | compliance review |

## 13. Backup and disaster recovery
- Back up PostgreSQL metadata and object storage snapshots.
- Maintain vector-store backup and recovery procedures.
- Validate restore operations in staging before production use.

## 14. Related documents
- [03-roles-and-permissions.md](./03-roles-and-permissions.md)
- [05-database-design.md](./05-database-design.md)
- [10-security-and-privacy.md](./10-security-and-privacy.md)
- [13-evaluation-and-testing.md](./13-evaluation-and-testing.md)
