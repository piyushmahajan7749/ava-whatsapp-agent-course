# Human Escalation System - Quick Start Guide

## 🚀 Ready to Use!

Your human escalation system is **fully implemented and configured**! Here's everything you need to know:

## 📱 Customer Service Contact

**WhatsApp Number:** +919876543210  
**Link:** https://wa.me/919876543210

This number will receive all escalated cases with pre-filled messages.

## ✅ What Triggers Escalation

The bot automatically detects and escalates when users:

### English Phrases:

- "I want a refund"
- "Give me my money back"
- "Your service is terrible"
- "I'm not satisfied"
- "Can I speak to a real person?"
- "Talk to your manager"
- "I was charged twice"
- "Wrong amount charged"
- "Cancel my order"
- "This is unacceptable"

### Hinglish Phrases (Your Primary User Base):

- "Mujhe refund chahiye"
- "Mera paisa wapas karo"
- "Ye service bahut bekaar hai"
- "Main satisfied nahi hoon"
- "Kisi insaan se baat karni hai"
- "Manager se baat karao"
- "Do baar charge ho gaya"
- "Galat amount charge kiya"
- "Order cancel karo"
- "Bahut galat hai ye"

## 🧪 Test It Right Now

### Quick Test (Router Only):

```bash
cd /Users/piyush/Projects/cx-agent
uv run python examples/test_escalation_router.py
```

This tests the router's ability to detect escalations (25+ test cases).

### Example Test Messages You Can Try:

**Test in WhatsApp:**

1. Send: "Mujhe refund chahiye"
2. Bot should respond with empathetic message + WhatsApp link
3. Link should open WhatsApp with pre-filled Hinglish message

**Test Different Scenarios:**

- Refund request: "I want my money back"
- Complaint: "Ye service bahut bekaar hai"
- Human request: "Kisi insaan se baat karni hai"
- Billing issue: "Do baar charge ho gaya"

## 📊 What the Bot Does

When escalation is detected, the bot:

1. ✅ **Stops trying to solve it** - No tool calls, no booking attempts
2. ✅ **Responds empathetically** - Caring, understanding language
3. ✅ **Provides WhatsApp link** - Pre-filled with user's concern
4. ✅ **Matches user's language** - English response for English, Hinglish for Hinglish
5. ✅ **Logs the escalation** - For analytics and monitoring

## 💬 Example Responses

### English User Says:

> "I want a refund"

**Bot Responds:**

```
I completely understand. I'm really sorry for the inconvenience.
Let me connect you with our customer service team right away who
can help with your refund request.

Please reach out to them directly here:
https://wa.me/919876543210?text=Hello,%20I%20need%20help%20with%20a%20refund%20request

They'll assist you promptly. Is there anything else I can help
clarify before you connect with them?
```

### Hinglish User Says:

> "Mujhe refund chahiye"

**Bot Responds:**

```
Main samajh sakti hoon. Mujhe bohot dukh hai aapko inconvenience
ke liye. Main aapko abhi hamari customer service team se connect
karti hoon jo aapke refund request mein help karenge.

Yahan se unse direct baat kar sakte ho:
https://wa.me/919876543210?text=Namaste,%20mujhe%20refund%20ke%20liye%20help%20chahiye

Wo jaldi se help karenge. Kuch aur clarify karna hai aapko?
```

## 🔍 Monitoring Escalations

Check your logs for escalation events:

```bash
# Look for escalation log entries
grep "ESCALATION DETECTED" logs/app.log

# Or in real-time
tail -f logs/app.log | grep "escalation"
```

**Log format:**

```
🚨 ESCALATION DETECTED - Loading ESCALATION_CONTEXT, tools disabled
Intent: escalation_needed
Stage: escalation_requested
Thread ID: 919876543210
Confidence: 1.0
```

## ⚠️ Important: What NOT to Escalate

The system is smart enough to know these are NOT escalations:

❌ "What is your refund policy?" (just asking)  
✅ "I want a refund" (actual request)

❌ "Refund ke baare mein batao" (informational)  
✅ "Mera paisa wapas do" (demand)

❌ "Tell me about your services" (inquiry)  
✅ "Your service is terrible" (complaint)

## 🎯 Customer Service Team Guidelines

When you receive escalated messages:

1. **Respond Quickly** - User is already frustrated, speed matters
2. **Stay Empathetic** - They're escalating because they need help
3. **Have Context** - The pre-filled message tells you the issue
4. **Resolve Thoroughly** - Don't make them escalate again
5. **Follow Up** - Check if issue was resolved satisfactorily

## 📈 Success Metrics to Track

Monitor these KPIs:

- **Escalation Volume** - How many per day/week?
- **Escalation Reasons** - What's the most common? (refunds? complaints?)
- **Resolution Time** - How fast does team respond?
- **Resolution Rate** - What % of escalations get resolved?
- **Re-escalation Rate** - Do users escalate again? (should be low)

## 🔧 Configuration (If Needed)

To change the customer service number:

```python
# src/ai_companion/core/knowledge.py

CUSTOMER_SERVICE_PHONE = "+919876543210"  # Change this
CUSTOMER_SERVICE_WHATSAPP = "https://wa.me/919876543210"  # And this
```

## 🆘 Troubleshooting

### Issue: Bot not detecting escalation

**Solution:** Check if user's phrasing matches examples. Add more keywords to router prompt if needed.

### Issue: False positives (normal questions trigger escalation)

**Solution:** Update distinction examples in `INTENT_ROUTER_PROMPT` in prompts.py

### Issue: WhatsApp link not working

**Solution:** Verify the number is correct and has WhatsApp Business enabled

### Issue: Wrong language response

**Solution:** Router should auto-detect language. Check if user's message is clearly English or Hinglish.

## 📚 Related Documentation

- Full implementation details: `docs/HUMAN_ESCALATION_IMPLEMENTATION.md`
- Router architecture: `docs/INTENT_ROUTING_IMPLEMENTATION.md`
- Testing guide: `examples/test_escalation_router.py`

## ✨ Quick Wins

This system will help you:

1. **Reduce frustration** - Users get human help immediately
2. **Prevent churn** - Complaints handled before users leave
3. **Improve satisfaction** - Empathetic responses build trust
4. **Save time** - Pre-filled messages speed up resolution
5. **Track issues** - Analytics show what needs improvement

## 🎉 You're All Set!

Your bot now has production-ready human escalation that:

- ✅ Works in English and Hinglish
- ✅ Detects refunds, complaints, and human requests
- ✅ Provides empathetic responses
- ✅ Seamlessly connects to customer service via WhatsApp
- ✅ Prevents bot errors during sensitive situations

**Test it, monitor it, and watch customer satisfaction improve!** 🚀

---

Need help? Check the logs or test with `examples/test_escalation_router.py`
