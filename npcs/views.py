from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import NPCPersonaForm
from .models import NPCProfile


@login_required
def edit_npc(request, pk):
    """Edit the persona/kill-switch of a party's NPC. Party leader/deputy/executive only
    (full behavior tuning, for any NPC, lives under the moderator section)."""
    npc = get_object_or_404(NPCProfile, pk=pk)
    party = npc.party

    can_manage_party = party is not None and party.can_user_manage(request.user)

    if not (can_manage_party or request.user.is_staff):
        messages.error(request, "You don't have permission to edit this NPC.")
        return redirect('parties:detail', pk=party.pk) if party else redirect('forum:index')

    if request.method == 'POST':
        form = NPCPersonaForm(request.POST, instance=npc)
        if form.is_valid():
            npc_instance = form.save(commit=False)
            if 'persona' in form.changed_data:
                npc_instance.persona_manually_edited = True
            npc_instance.save()
            messages.success(request, 'NPC updated successfully!')
            return redirect('parties:detail', pk=party.pk) if party else redirect('forum:index')
    else:
        form = NPCPersonaForm(instance=npc)

    context = {
        'form': form,
        'npc': npc,
        'party': party,
    }
    return render(request, 'edit_npc.html', context)
