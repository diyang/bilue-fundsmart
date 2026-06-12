# Seed Complaints

Three sample complaints for the FundSmart AI triage exercise. All content is synthetic. Any resemblance to real customers, staff, or cases is coincidental.

Use these as starters for your own synthetic data generation. Your additional test cases should cover shapes these three do not.

**What makes a good seed case:** every signal needed to triage the complaint is in the message itself. A good triage system should not need to look up external contracts, case histories, or regulatory documents to assign a category, severity, vulnerability assessment, and routing. Your synthetic data should meet the same bar.

---

## Sample 1 — Email

**Channel:** Email
**Received:** 2026-04-14 10:32 AEST
**Customer ID:** CUST-48291
**Subject:** Wrong information from your staff caused a missed payment

```
Hi,

I'm writing to make a formal complaint.

On Wednesday 8 April I called your support line to change my direct
debit from my Commonwealth Bank account to my ING account. The woman
I spoke to (I didn't catch her name, sorry) confirmed she had
actioned the change and said it would take 2 business days to take
effect. I moved the money across over the weekend on the strength of
what she told me.

Today my monthly repayment of $612 came out of the Commonwealth
account, which I had nearly emptied. It bounced. My bank has charged
me a $15 dishonour fee. I then called FundSmart again and a different
agent told me the change had never actually been processed because
direct debit changes have to be done through the app, not over the
phone. Nobody told me that last week. If they had, I would have done
it through the app.

I am really not happy. I want:

1. The missed payment recorded as not my fault, so it doesn't end up
   on my credit file.
2. Any late fees on my loan waived.
3. The $15 dishonour fee covered by FundSmart, since it happened
   because of what your staff member told me.
4. Some assurance this won't happen to other people.

Please confirm receipt and let me know what happens next.

Regards,
Sarah B.
```

---

## Sample 2 — In-App Message

**Channel:** In-app (FundSmart mobile app, messaging thread)
**Received:** 2026-04-15 22:47 AEST
**Customer ID:** CUST-51104
**Thread context:** First message in a new thread. Customer has an active 5-year personal loan, 18 months in, currently up to date on payments.

```
hi. look i dont even know if this is the right place to ask. things
have been really rough since my wife moved out in feb, im trying to
keep up with the loan payments but between the mortgage and the two
kids and daycare its not working. i got a pay cut at work in march
too, nothing massive but on top of everything else its been too much.

is there any way to pause the loan for a few months or make the
repayments smaller? i dont want to miss one and wreck my credit.
honestly i havent slept properly in weeks. ive been looking at my
statements at 2am trying to figure it out.

i dont really want to talk on the phone if that can be avoided. ty
```

---

## Sample 3 — Call Transcript (excerpt)

**Channel:** Inbound call transcript, auto-transcribed
**Received:** 2026-04-17 14:08 AEST
**Customer ID:** CUST-33872
**Agent:** Priya K. (frontline)
**Duration:** 6 minutes 42 seconds (excerpt below is first 2 minutes)
**Note:** Transcription quality is auto-generated and may contain errors.

```
AGENT: Thanks for calling FundSmart, this is Priya, how can I help?

CUSTOMER: Yeah hi look I'm, I'm really not happy. I took out a loan
with you guys in November last year, the fifteen thousand one, for
the car. And I've just been to see a financial counsellor because
I can't afford any of it anymore, and she's saying there's no way
I should have got that loan in the first place based on what I was
earning at the time.

AGENT: I'm sorry to hear that, I can definitely help, can you give
me your customer ID?

CUSTOMER: Yeah it's uh three three eight seven two. Look I told the
person on the application, the chat thing, I told them I was doing
casual shifts only because I'd been let go from my main job, and
they still went ahead with it. The counsellor says that shouldn't
have happened, that you guys have to actually check if I can afford
it. She said something about responsible lending obligations.

AGENT: OK I've got you, let me pull up your file.

CUSTOMER: I'm behind two payments now. I've had calls from your
collections team. I've got a seven year old, I can't, I can't deal
with this. I want to put in a formal complaint and she said if it
doesn't get sorted we're going to AFCA.

AGENT: Right, OK, absolutely, I understand. So I'm going to log
this as a formal complaint now so we've got it on record, and
then...
```

---

## Notes on These Three Samples

The three cases are deliberately chosen to span shape, severity, and vulnerability.

- Sample 1 is a **service complaint without vulnerability or regulatory flags**. Customer is frustrated but fine. Your system should classify it correctly and draft a proportionate response. It should not invent hardship or compliance issues that are not there.
- Sample 2 is a **subtle hardship case with meaningful vulnerability signals** that a careless triage step could miss. The customer is still current on payments but at risk. The stated channel preference (no phone) matters for the routing decision.
- Sample 3 is a **high-severity regulatory case** with a live AFCA threat, arrears, and clear vulnerability context. Multiple signals to catch.

A good synthetic test set will also include shapes these three do not cover. For example:

- Very short complaints with minimal context.
- Vague rants with no clear issue, where the customer is upset but not asking for anything specific.
- Multi-issue complaints where the headline issue is not the most important one.
- Complaints that look serious but are routine, and routine complaints that hide something serious.
- Customers whose first language is not English, or whose writing is hard to parse.
- Complaints that contain threats, abuse, or self-harm signals.
- Complaints that are actually about the wrong company or product.
- Customers who have contradicted themselves across the message.

How you structure your synthetic data, what shapes you include, and what distribution you choose, is part of what we are evaluating.
